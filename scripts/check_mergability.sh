#!/bin/sh

# How to run:
# * Install the gh cli and run `gh login`: https://github.com/cli/cli/
# * install black isort usort pyupgrade and whatever other tools you want to
#   play with in your active virtualenv
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

generate_report () {
  # checkout a branch, try to merge each of the open PRs, write the results to
  # a CSV file
  base="${1:-master}"
  quiet=$2

  git checkout -q $base

  report_file=../report-$base.csv
  [ -e $report_file ] && [ -z "$quiet" ] && {
    prompt_or_summary "$report_file exists, overwrite?"
  }

  echo "number,updated,title,state,clean,conflicting" > $report_file
  report () {
    echo "$1,$2,\"$3\",$4,$5,$6" >> $report_file
  }

  jq -r '.[] | "\(.number) \(.updatedAt) \(.title)"' < ../prs.json | while read number updated title; do
    [ -n "$quiet" ] || echo "trying pr/$number $updated $title"
    head_sha=$(git rev-parse HEAD)
    git merge -q --no-ff --no-edit pr/$number 2>&1 1>/dev/null | grep -v preimage
    if [ -e .git/MERGE_HEAD ] ;then
      # merge failed, clean lines staged and conflicting lines in working
      # tree
      merged_lines=$(git diff --cached --numstat | awk -F'	' '{sum+=$1;} END{print sum;}')
      conflicting_lines=$(git diff | sed -n -e '/<<<<<<< HEAD/,/=======$/p' -e '/=======$/,/>>>>>>> pr/p' | wc -l)
      conflicting_lines=$(($conflicting_lines-4)) # account for markers included in both sed expressions
      [ -n "$quiet" ] || echo "#$number failed merging merged_lines=$merged_lines conflicting_lines=$conflicting_lines"
      git merge --abort
      report $number $updated "$title" failed $merged_lines $conflicting_lines
    else
      [ -n "$quiet" ] || echo "#$number merged fine"
      #git show HEAD --oneline --stat
      git reset -q --hard $head_sha
      report $number $updated "$title" succeeded 0 0
    fi
  done
}

cd qutebrowser

# run as `$0 some-branch` to report on merging all open PRs to a branch you
# made yourself. Otherwise run without args to try with a bunch of builtin
# configurations.
if [ -n "$1" ] ;then
  generate_report "$1"
else
  usort () { env usort format "$@"; }
  pyupgrade () { git ls-files | grep -F .py | xargs pyupgrade --py37-plus; }
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
  tmp-black_isort_pyupgrade black usort pyupgrade
  qt6-v2 true"
  #tools="tmp-black_isort black isort
  #tmp-black_usort black usort"

  prompt_or_summary "Generate report for all tool configurations?"
  clean_branches

  echo "$tools" | while read branch cmds; do
    echo "$branch"
    git checkout -q "$branch" 2>/dev/null || git checkout -q -b "$branch" origin/master
    echo "$cmds" | tr ' ' '\n' | while read cmd; do
      $cmd qutebrowser tests
      git commit -am "$cmd"
    done
    generate_report "$branch" y
  done
fi

summary

# todo:
# * see if we can run formatters on PR branches before/while merging
# * do most stuff based off of qt6-v2 instead of master, not like most PRs
#   will be merged to pre-3.0 master anyway
# notes:
# after merging qt6-v2 would merging old PRs to old master then somehow merging
#   the PR merge commit up to the new master easier than rebasing the PR?
# there is a filter attribute you can use to re-write files before committing.
#   For this use case probably the same as rebase -i --exec then merge?
#   >See "Merging branches with differing checkin/checkout attributes" in gitattributes(5)
