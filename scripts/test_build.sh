#!/usr/bin/env sh

work_tree="$(realpath "$(dirname $0)/..")"
cur_branch="$(git branch --show-current)"

echo "work_tree: $work_tree"
echo "'after' branch: $cur_branch"
echo "'before' branch: main"

cd "$work_tree"
stash_output="$(git stash)"
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
# Example packing workflows (review changes in output and any changes to build
#   commands needed):
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
  eval $cmd >&2
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

  # Could also do `pip install -t ... .` and skip the separate wheel build.
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

################
# qutebrowser-git aur package
################
aur_package() {
  dest="$1"
  # This package script is split into two parts, build and package.
  # The build part runs `setup.py build`, but the package part seems to call
  # that as a pre-req of `setup.py install` anyway, so I'm not sure what the
  # point of it is.
  # The package step install the python package to a directory (using a
  # makefile command).
  # Tentative recommendation:
  # * remove setup.py invocation from build step if not needed
  # * change makefile command to use `pip3 install -t ... .`

  # https://aur.archlinux.org/cgit/aur.git/tree/PKGBUILD?h=qutebrowser-git
  cd "$work_tree"
  rm -r build dest
  python3 -m pip install asciidoc
  # "build" -- this is the same as compare_build but we prepare docs too
  # Requires asciidoc and docbook-xsl
  python scripts/asciidoc2html.py
  a2x -L -f manpage doc/qutebrowser.1.asciidoc
  # The PKGBUILD calls setup.py directly. I'm deferring to the makefile here
  # so that we can run a different command based on the branch we are on. Also
  # this step doesn't seem to affect the package output.
  make -f misc/Makefile all

  # "package"
  # This looks like it does `setup.py build` as part of `install` anyway
  # Requires distutils for byte compiling with `setup.py install`
  # Prints a banner warning saying setup.py install will stop working October
  # 31 and points to: https://blog.ganssle.io/articles/2021/10/setup-py-deprecated.html
  # Neither pip install of build let you specify an optimisation level for
  #   byte compiling.
  make -f misc/Makefile DESTDIR="$dest" PREFIX=/usr install

  git reset --hard HEAD
}
compare_package_aur() {
  # This (setup.py install) sometimes fails when byte compiling with
  # "ModuleNotFoundError: No module named 'distutils'". I'm not sure why,
  # sometimes it succeeds though!
  run_in_venv before main "python3 -m pip install setuptools && aur_package $scratch_dir/aur-before"
  cd "$scratch_dir/aur-before"
  # Remove optimized compiled files to make the diff smaller -- known
  # difference.
  ls -R | grep -v "opt-1.pyc" > ../aur-before.list
  cd -

  run_in_venv after "$cur_branch" "aur_package $scratch_dir/aur-after"
  cd "$scratch_dir/aur-after"
  ls -R > ../aur-after.list

  diff -u ../aur-before.list ../aur-after.list
  cd -

  # --- ../aur-before.list  2025-06-08 16:11:00.425813175 +1200
  # +++ ../aur-after.list   2025-06-08 16:11:17.941359552 +1200
  # @@ -17,7 +17,7 @@
  #
  #  ./usr/lib/python3.13/site-packages:
  #  qutebrowser
  # -qutebrowser-3.5.0-py3.13.egg-info
  # +qutebrowser-3.5.0.dist-info
  #
  #  ./usr/lib/python3.13/site-packages/qutebrowser:
  #  api
  # @@ -727,14 +727,19 @@
  #  utils.cpython-313.pyc
  #  version.cpython-313.pyc
  #
  # -./usr/lib/python3.13/site-packages/qutebrowser-3.5.0-py3.13.egg-info:
  # -dependency_links.txt
  # +./usr/lib/python3.13/site-packages/qutebrowser-3.5.0.dist-info:
  # +direct_url.json
  #  entry_points.txt
  # -PKG-INFO
  # -requires.txt
  # -SOURCES.txt
  # +INSTALLER
  # +licenses
  # +METADATA
  # +RECORD
  # +REQUESTED
  #  top_level.txt
  # -zip-safe
  # +WHEEL
  # +
  # +./usr/lib/python3.13/site-packages/qutebrowser-3.5.0.dist-info/licenses:
  # +LICENSE
  #
  #  ./usr/share:
  #  applications
  # @@ -837,6 +842,7 @@
  #  mkvenv.py
  #  opengl_info.py
  #  open_url_in_instance.sh
  # +test_build.sh
  #  utils.py
  #
  #  ./usr/share/qutebrowser/userscripts:
}


# Comparisons of primitive build/install commands https://github.com/qutebrowser/qutebrowser/pull/8560#issuecomment-2934333806
#compare_editable
#compare_build
#compare_install

# Comparisons of packaging workflows
compare_package_aur

# Restore work tree
cd "$work_tree"
checkout "$cur_branch"
if [ "$stash_output" != "No local changes to save" ] ;then
  git stash pop
fi

