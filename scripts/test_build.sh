#!/usr/bin/env sh

work_tree="$(realpath "$(dirname $0)/..")"
cur_branch="$(git branch --show-current)"

echo "work_tree: $work_tree"
echo "'after' branch: $cur_branch"
echo "'before' branch: main"

cd "$work_tree"
git stash
cd -

scratch_dir="/tmp/qute_test_build"
[ -e "$scratch_dir" ] && rm -r "$scratch_dir"
mkdir "$scratch_dir"
cd "$scratch_dir"

# From: https://packaging.python.org/en/latest/guides/modernize-setup-py-project/#should-setup-py-be-deleted
#
# Deprecated                  |   Recommendation
# ----------------------------|------------------------------------
# python setup.py install     | python -m pip install .
# python setup.py develop     | python -m pip install --editable .
# python setup.py sdist       | python -m build
# python setup.py bdist_wheel | python -m build
#
# What about setup.py build? What are sdist and bdist_wheel?
# build -s writes a tar file (with even the files that aren't in git)
# buld -w seems to have a similar structure to setup.py build
#
# TODO: examine differences (looks pretty minor, just a few metadata files?)
# Can also compare `pip3 show -v qutebrowser`
# TODO: look at updating adapting makefile and packaging workflows
#
# Example packing workflows:
# * https://aur.archlinux.org/cgit/aur.git/tree/PKGBUILD?h=qutebrowser-git
# * https://gitlab.archlinux.org/archlinux/packaging/packages/qutebrowser/-/blob/main/PKGBUILD?ref_type=heads
# * https://github.com/qutebrowser/qutebrowser-debian/blob/master/debian/rules
# * https://github.com/flathub/org.qutebrowser.qutebrowser/blob/master/org.qutebrowser.qutebrowser.yml#L85

checkout() {
  cd "$work_tree"
  git checkout "$1"
  cd -
}

activate() {
  . $1/bin/activate
}

################
# pip install -e with pure setup.py vs pyproject.toml
################
run_in_venv() {
  venv="$1"
  branch="$2"
  cmd="$3"

  cd "$scratch_dir"
  python3 -m venv "$venv"
  activate "$venv"
  checkout "$branch" >&2
  $cmd >&2
  cd "$scratch_dir/$venv"
  ls -R > ../"$venv".list
  cd - >&2
  deactivate
  echo "$scratch_dir/$venv".list
}

compare_editable() {
  file_list_before="$(run_in_venv before main "pip install -e $work_tree")"
  if [ -e "$work_tree/pyproject.toml" ] ;then
    # Odd, when doing pip install -e on main I see messages like:
    #     Preparing editable metadata (pyproject.toml) ... done
    #     Building editable for qutebrowser (pyproject.toml) ... done
    # But there is no pyproject.toml, which this check confirms.
    echo "Err: pyproject.toml found on main"
    exit 1
  fi
  file_list_after="$(run_in_venv after "$cur_branch" "pip install -e $work_tree")"
  diff -u "$file_list_before" "$file_list_after"
}

compare_editable

################
# setup.py build vs python3 -m build --wheel
# The obvious difference is that one produces a wheel (and source tarball),
# one produces a source tree. The wheel has mostly the same contents as the
# tree from `setup.py build` though.
################
compare_build() {
  python3 -m venv build
  activate build
  pip3 install build setuptools
  
  cd "$work_tree"
  checkout main
  python3 setup.py -q build -b "$scratch_dir/build_before"
  
  checkout "$cur_branch"
  python3 -m build -w -o "$scratch_dir/wheel" >/dev/null
  cd "$scratch_dir"
  mkdir build_after
  cd build_after
  unzip -q ../wheel/*
  
  ls -R > ../build_after.list
  cd ../build_before/lib
  ls -R > ../../build_before.list
  cd ../..
  diff -u build_before.list build_after.list
}

compare_build

################
# setup.py install
################
# is this just going to be the same process as editable?
setuppy_install() {
  cd $work_tree
  pip3 install setuptools
  python3 setup.py install
}

compare_install() {
  file_list_before="$(run_in_venv before main setuppy_install)"

  python3 -m venv build
  activate build
  pip3 install build setuptools
  checkout "$cur_branch"
  cd "$work_tree"
  python3 -m build -w -o "$scratch_dir/wheel" >/dev/null
  # Have to install setuptools in this "after" venv to make the diff smaller,
  # as it's required to be in the "before" one to call setup.py.
  file_list_after="$(run_in_venv after "$cur_branch" "pip install --no-deps setuptools $scratch_dir/wheel/*")"

  diff -u "$file_list_before" "$file_list_after"
}

compare_install

# Restore work tree
cd "$work_tree"
checkout "$cur_branch"
git stash pop

