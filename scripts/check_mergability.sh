#!/bin/sh

# How to run:
# * Install the gh cli and run `gh login`: https://github.com/cli/cli/
# * install black isort usort pyupgrade and whatever other tools you want to
#   play with in your active virtualenv
# * also requires "sponge" from moreutils
# * move to a new folder for the script to work in: `mkdir pr_mergability && cd pr_mergability`
# * ../scripts/check_mergability.sh
#
# It'll clone the qutebrowser repo, fetch refs for all the open PRs, checkout
# a branch, run auto formatters, try to merge each PR, report back via CSV
# how badly each merge filed (via "number of conflicting lines").
#
# For details of what auto formatters are ran see the `tools` variable down
# near the bottom of the script.
#
# If you've checked out a branch and ran auto-formatters or whatever on it
# manually and just want the script to try to merge all PRs you can call it
# with the branch name and it'll do so. Remember to go back up to the work dir
# before calling the script.
#
# If it's been a few days and PRs have been opened or merged delete `prs.json`
# from the working dir to have them re-fetched on next run.
# If PRs have had updates pushed you'll have to update the refs yourself or
# nuke the whole clone in the work dir and let the script re-fetch them all.

# requires the github binary, authorized, to list open PRs.
command -v gh > /dev/null || {
  echo "Error: Install the github CLI, gh, make sure it is in PATH and authenticated."
  exit 1
}
# requires some formatting tools available. The are all installable via pip.
all_formatters="black isort usort pyupgrade"
for cmd in $all_formatters; do
  command -v $cmd >/dev/null || {
    echo "Error: Requires all these tools to be in PATH (install them with pip): $all_formatters"
    exit 1
  }
done

[ -e qutebrowser/app.py ] && {
  echo "don't run this from your qutebrowser checkout. Run it from a tmp dir, it'll checkout out a new copy to work on"
  exit 1
}

TTY="$(tty)"
DO_PAUSE="no"
maybepause () {
  msg="$1"
  force="$2"
  if [ -n "$force" ] ;then
    DO_PAUSE="yes"
  elif [ "$DO_PAUSE" = "yes" ] ;then
    true
  else
    return
  fi

  echo "$1, investigate in another terminal, continue? [Step|Continue|Quit]"
  read response < $TTY
  case "$response" in
    [Cc]*) DO_PAUSE="no";;
    [Qq]*) exit 0;;
    *) return;;
  esac
}

[ -d qutebrowser ] || {
  git clone git@github.com:qutebrowser/qutebrowser.git
  cd qutebrowser
  git config --local merge.conflictstyle merge
  git config --local rerere.enabled false
  cd -
}

[ -e prs.json ] || {
  # (re-)fetch list of open PRs. Pull refs for any new ones.
  # Resets master and qt6-v2 in case they have changed. Does not handle
  # fetching new changes for updated PRs.
  echo "fetching open PRs"
  gh -R qutebrowser/qutebrowser pr list -s open --json number,title,mergeable,updatedAt -L 100 > prs.json
  cd qutebrowser
  git fetch
  git checkout master && git pull
  git checkout qt6-v2 && git pull
  # this is slow for a fresh clone, idk how to fetch all pull/*/head refs at once
  jq -r '.[] | "\(.number) \(.updatedAt) \(.title)"' < ../prs.json | while read number updated title; do
    git describe pr/$number >/dev/null 2>&1 || git fetch origin refs/pull/$number/head:pr/$number
  done
  cd -
}

python3 <<"EOF"
import json
from collections import Counter
import rich

with open("prs.json") as f: prs=json.load(f)

rich.print(Counter([p['mergeable'] for p in prs]))
# Counter({'MERGEABLE': 29, 'CONFLICTING': 45})
EOF

summary () {
  # Summarize the accumulated report CSVs
  # Should be the last thing we do since it goes back up to the report dir
  cd - >/dev/null
  python3 <<"EOF"
import csv, glob

def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))

for report in sorted(glob.glob("report-*.csv")):
    rows = read_csv(report)
    succeeded = len([row for row in rows if row["state"] == "succeeded"])
    failed = len([row for row in rows if row["state"] == "failed"])
    print(f"{report} {succeeded=} {failed=}")
EOF
}

prompt_or_summary () {
    printf "$1 [Yn]: "
    read ans
    case "$ans" in
      [nN]*)
        summary
        exit 0
        ;;
      *) true;;
    esac
}

# format tool "aliases", where needed
usort () { env usort format "$@"; }
isort () { env isort -q "$@"; }
black () { env black -q "$@"; }
pyupgrade () { git ls-files | grep -F .py | xargs pyupgrade --py37-plus; }

generate_report () {
  # checkout a branch, try to merge each of the open PRs, write the results to
  # a CSV file
  base="${1:-master}"
  quiet="$2"
  rewrite_strategy="$3"
  cmds="$4"
  pr="$5"
  report_file=../report-$base.csv

  # prefix for working branch when we are going to re-write stuff so we don't
  # mess up the pr/* branches and have to re-fetch them.
  [ -n "$rewrite_strategy" ] && {
    prefix="tmp-rewrite-"
    report_file=../report-$base-$rewrite_strategy.csv
  }

  git checkout -q $base

  [ -e $report_file ] && [ -z "$quiet" ] && {
    prompt_or_summary "$report_file exists, overwrite?"
  }

  echo "number,updated,title,state,clean,conflicting" > $report_file
  report () {
    echo "$1,$2,\"$3\",$4,$5,$6" >> $report_file
  }

  head_sha=$(git rev-parse HEAD)
  jq -r '.[] | "\(.number) \(.updatedAt) \(.title)"' < ../prs.json | while read number updated title; do
    [ -n "$pr" ] && [ "$pr" != "$number" ] continue
    [ -n "$quiet" ] || echo "trying ${prefix}pr/$number $updated $title"
    git reset -q --hard $head_sha

    case "$rewrite_strategy" in
      rebase|merge)
        # Only attempt branches that actually merge cleanly with master.
        # Theoretically it wouldn't hurt to do all of them but a) running
        # black via the filter driver is slow b) rebase_with_formatting needs
        # some work to handle more errors in that case (the "git commit -qam
        # 'fix lint" bit at least needs to look for conflict markers)
        # I'm hardcoding master because of a lack of imagination.
        grep "^$number" ../report-master.csv | grep failed && {
          echo "pr/$number succeeded already in ../report-master.csv, skipping"
          continue
        }
        rebase_with_formatting "$number" "$base" "$cmds" "$prefix" "$rewrite_strategy" || {
          report $number $updated "$title" failed 999 999
          continue
        }
        ;;
      '')
        true
        ;;
      *)
        echo "Unknown rewrite strategy '$rewrite_strategy'"
        exit 1
        ;;
    esac

    git merge -q --no-ff --no-edit ${prefix}pr/$number 2>&1 1>/dev/null | grep -v preimage
    if [ -e .git/MERGE_HEAD ] ;then
      # merge failed, clean lines staged and conflicting lines in working
      # tree
      merged_lines=$(git diff --cached --numstat | awk -F'	' '{sum+=$1;} END{print sum;}')
      conflicting_lines=$(git diff | sed -n -e '/<<<<<<< HEAD/,/=======$/p' -e '/=======$/,/>>>>>>> pr/p' | wc -l)
      conflicting_lines=$(($conflicting_lines-4)) # account for markers included in both sed expressions
      [ -n "$quiet" ] || echo "#$number failed merging merged_lines=$merged_lines conflicting_lines=$conflicting_lines"
      maybepause "merge of ${prefix}pr/$number into $base failed"
      git merge --abort
      report $number $updated "$title" failed $merged_lines $conflicting_lines
    else
      [ -n "$quiet" ] || echo "#$number merged fine"
      #git show HEAD --oneline --stat
      report $number $updated "$title" succeeded 0 0
    fi
  done
}

rebase_with_formatting () {
  number="$1"
  base="$2"
  cmds="$3"
  prefix="${4:-tmp-rewrite-}"
  strategy="$5"

  # We need to apply formatting to PRs and base them on a reformatted base
  # branch.
  # I haven't looked into doing that via a merge but here is an attempt
  # doing a rebase.
  # Rebasing directly on to a formatted branch will fail very easily when it
  # runs into a formatting change. So I'm using git's "filter" attribute to
  # apply the same formatter to the trees corresponding to the
  # commits being rebased. Hopefully if we apply the same formatter to the
  # base branch and to the individual commits from the PRs we can minimize
  # conflicts.
  # An alternative to using the filter attribute might be to use something
  # like the "darker" tool to re-write the commits. I suspect that won't
  # help with conflicts in the context around changes though.

  # Checkout the parent commit of the branch then apply formatting tools to
  # it. This will provide a target for rebasing which doesn't have any
  # additional drift from changes to master. After that then we can rebase
  # the re-written PR branch to the more current, autoformatted, master.
  # TODO: It might be possible to skip the intermediate base branch.
  git checkout -b tmp-master-rewrite-pr/$number `git merge-base origin/master pr/$number`
  echo "$cmds" | tr ' ' '\n' | while read cmd; do
    $cmd qutebrowser tests
    git commit -am "dropme! $cmd" # mark commits for dropping when we rebase onto the more recent master
  done

  git checkout -b ${prefix}pr/$number pr/$number

  # Setup the filters. A "smudge" filter is configured for each tool then we
  # add the required tools to a gitattributes file. And make sure to clean
  # it up later.
  # Running the formatters as filters is slower than running them directly
  # because they seem to be run on the files serially. TODO: can we
  # parallelize them?
  # Maybe just adding a wrapper around the formatters that caches the output
  # would be simpler. At least then you just have to sit through them once.
  git config --local filter.rewrite.smudge "filter-cache"
  printf "*.py" > .git/info/attributes
  printf " filter=rewrite" >> .git/info/attributes
  echo >> .git/info/attributes

  mkdir filter-tools 2>/dev/null
  cat > filter-tools/filter-cache <<EOF
#!/bin/sh
# Script to add as filter for git while rebasing.
# Runs the configured tools in sequence, caches the result of each tool in
# case you find yourself running through this proecss lots while working on
# it.

cmds="$cmds"
inputf="\$(mktemp --suffix=rebase)"
cat > "\$inputf"

# TODO: de-dup these with the parent script?
# Can use aliases here?
# Call with the file drectly instead of using stdin?
usort () { env usort format -; }
black () { env black -q -; }
isort () { env isort -q -; }
pyupgrade () { env pyupgrade --py37-plus -; }

run_with_cache () {
  inputf="\$1"
  cmd="\$2"
  input_hash="\$(sha1sum "\$inputf" | cut -d' ' -f1)"

  mkdir -p "/tmp/filter-caches/\$cmds/\$cmd" 2>/dev/null
  outputf="/tmp/filter-caches/\$cmds/\$cmd/\$input_hash"

  [ -e "\$outputf" ] || \$cmd < "\$inputf" > "\$outputf"

  cat "\$outputf"
}

echo "\$cmds" | tr ' ' '\n' | while read cmd; do
  run_with_cache \$inputf "\$cmd" | sponge \$inputf
done

cat "\$inputf"
EOF
  chmod +x filter-tools/filter-cache
  export PATH="$PWD/filter-tools:$PATH"

  # not sure why I had to do the extra git commit in there, there are some
  # changes left in the working directory sometimes? TODO: change to a
  # commit --amend -C HEAD after confirming overall results
  # Need to revisit some assumptions about the smudge filter, does it always
  # leave changes in the working tree?
  # TODO: look for conflict markers before merging
  # `theirs` here applies to the incoming commits, so the branch being
  # rebased. Without that changes made by the smudge filter seem to conflict
  # with later changes by the smudge filter. See #7312 for example
  git rebase -q -X theirs -X renormalize --exec 'git commit -qam "fix lint" || true' tmp-master-rewrite-pr/$number
  exit_code="$?"
  [ $exit_code -eq 0 ] || {
    maybepause "rebase -X renormalize of ${prefix}pr/$number onto tmp-master-rewrite-pr/$number failed"
    git rebase --abort
  }
  git branch -D tmp-master-rewrite-pr/$number
  rm .git/info/attributes

  [ $exit_code -eq 0 ] || return $exit_code

  if [ "$strategy" = "rebase" ] ;then
    # now transplant onto the actual upstream branch -- might have to drop this
    # if it causes problems.
    EDITOR='sed -i /dropme/d' git rebase -qi "$base" || {
      maybepause "rebase of ${prefix}pr/$number onto $base failed"
      git rebase --abort
      return 1
    }
  fi

  git checkout -q $base
}

cd qutebrowser

# run as `$0 some-branch` to report on merging all open PRs to a branch you
# made yourself. Otherwise run without args to try with a bunch of builtin
# configurations.

strategy=""
pull_request=""
while [ -n "$1" ] ;do
  case "$1" in
    -s|--rewrite-strategy)
      shift
      [ -n "$1" ] || {
        echo "What strategy?"
        exit 1
      }
      strategy="$1"
      ;;
    -p|--pull-request)
      shift
      [ -n "$1" ] || {
        echo "Which PR?"
        exit 1
      }
      pull_request="$1"
      ;;
    -*)
      echo "Unknown argument '$1'"
      exit 1
      ;;
    *)
      break
      ;;
  esac
  shift
done

if [ -n "$1" ] ;then
  generate_report "$1"
else
  clean_branches () {
    # only clean up tmp- branches in case I run it on my main qutebrowser
    # checkout by mistake :)
    git checkout master
    git reset --hard origin/master
    git branch -l | grep tmp- | grep -v detached | while read l; do git branch -qD $l ;done
  }

  # pre-defined auto-formatter configurations. Branches will be created as
  # needed.
  # format: branch tool1 tool2 ...
  tools="master true
  tmp-black black
  tmp-black_isort black isort
  tmp-black_usort black usort
  tmp-black_pyupgrade black pyupgrade
  tmp-black_isort_pyupgrade black isort pyupgrade
  tmp-black_usort_pyupgrade black usort pyupgrade
  qt6-v2 true"
  tools="tmp-black black"

  prompt_or_summary "Generate report for all tool configurations?"
  clean_branches

  echo "$tools" | while read branch cmds; do
    echo "$branch"
    git checkout -q "$branch" 2>/dev/null || git checkout -q -b "$branch" origin/master
    echo "$cmds" | tr ' ' '\n' | while read cmd; do
      $cmd qutebrowser tests
      git commit -am "$cmd"
    done
    generate_report "$branch" y "$strategy" "$cmds" "$pull_request"
  done
fi

summary

# todo:
# * see if we can run formatters on PR branches before/while merging
# * do most stuff based off of qt6-v2 instead of master, not like most PRs
#   will be merged to pre-3.0 master anyway
# * for strategies where we skip PRs that failed in master include them in the
#   report to for reference. With a marker to that affect and a total diffstat
#   so we can see how big they are
# * *try the more simplistic "Run the formatter on all PR branches then merge"
#   instead of trying to do it via a rebase*
# * try rebasing them to an autoformatted qt6-v2 branch
# notes:
# after merging qt6-v2 would merging old PRs to old master then somehow merging
#   the PR merge commit up to the new master easier than rebasing the PR?
# there is a filter attribute you can use to re-write files before committing.
#   For this use case probably the same as rebase -i --exec then merge?
#   >See "Merging branches with differing checkin/checkout attributes" in gitattributes(5)
# if we go with the strategy of rebasing PRs on formatted commits how to deal
#   with stopping isort making import loops on every damn PR. Still need to try
#   rebasing directly on the latest formatted master instead of doing the
#   intermediated one.
