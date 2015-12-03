import pytest
from qutebrowser.browser import adblock
from qutebrowser.config import config
from qutebrowser.utils import objreg
import os
import zipfile
import io

# @pytest.yield_fixture
# def default_config():
#     """Fixture that provides and registers an empty default config object."""
#     config_obj = config.ConfigManager(configdir=None, fname=None, relaxed=True)
#     objreg.register('config', config_obj)
#     yield config_obj
#     objreg.delete('config')

def create_text_files(files_names, directory):
    """Returns a list of created text files"""
    directory = str(directory)
    created_files = []
    for file_name in files_names:
        test_file = os.path.join(directory, file_name)
        with open(test_file, 'w') as f :
            f.write('inside ' + file_name)
        created_files.append(test_file)
    return created_files

def create_zipfile(files_names, directory):
    """Returns a zipfile populated with created files and its name"""
    directory = str(directory)
    files = create_text_files(files_names, directory)
    # include created files in a ZipFile
    zipfile_name = os.path.join(directory,'test.zip')
    with zipfile.ZipFile(zipfile_name, 'w') as zf:
        for file_name in files :
            zf.write(file_name, arcname=os.path.basename(file_name))
            # Removes path from file name
    return zf, zipfile_name

class TestGuessZipFilename :
    """ Test function adblock.guess_zip_filename() """

    def test_with_single_file(self, tmpdir):
        """Zip provided only contains a single file"""
        zf = create_zipfile(['testa'], tmpdir)[0]
        assert adblock.guess_zip_filename(zf) == 'testa'
        # guess_zip_filename doesn't include the root slash /
        # whereas os.path.join() does, so we exclude first character

    def test_with_multiple_files(self, tmpdir):
        """Zip provided contains multiple files including hosts"""
        zf = create_zipfile(['testa','testb','hosts','testc'], tmpdir)[0]
        assert adblock.guess_zip_filename(zf) == 'hosts'
        # guess_zip_filename doesn't include the root slash /
        # whereas os.path.join() does, so we exclude first character

    def test_without_hosts_file(self, tmpdir):
        """Zip provided does not contain any hosts file"""
        zf = create_zipfile(['testa','testb','testd','testc'], tmpdir)[0]
        with pytest.raises(FileNotFoundError):
            adblock.guess_zip_filename(zf)

class TestGetFileObj :
    """Test Function adblock.get_fileobj()"""

    def test_with_zipfile(self, tmpdir):
        zf_name = create_zipfile(['testa','testb','hosts','testc'], tmpdir)[1]
        zipobj = open(zf_name, 'rb')
        assert adblock.get_fileobj(zipobj).read() == "inside hosts"

    def test_with_text_file(self, tmpdir):
        test_file = open(create_text_files(['testfile'], tmpdir)[0], 'rb')
        assert adblock.get_fileobj(test_file).read() == "inside testfile"

class TestIsWhitelistedHost :

    # def test_with_no_whitelist(self):
    #     config_obj = config.ConfigManager(configdir=None, fname=None, relaxed=True)
    #     objreg.register('config', config_obj)
    #     assert adblock.is_whitelisted_host('pimpmytest.com') == False
    #     objreg.delete('config')

    def test_with_no_whitelist(self):
        # FIXME Behaves like a mismatch
        config_obj = config.ConfigManager(configdir=None, fname=None, relaxed=True)
        default_config.remove_option('content','host-blocking-whitelist')
        objreg.register('config', config_obj)
        assert adblock.is_whitelisted_host('pimpmytest.com') == False
        objreg.delete('config')

    def test_with_match(self):
        config_obj = config.ConfigManager(configdir=None, fname=None, relaxed=True)
        config_obj.set('conf','content','host-blocking-whitelist','qutebrowser.org')
        objreg.register('config', config_obj)
        assert adblock.is_whitelisted_host('qutebrowser.org') == True
        objreg.delete('config')

    def test_without_match(self):
        config_obj = config.ConfigManager(configdir=None, fname=None, relaxed=True)
        config_obj.set('conf','content','host-blocking-whitelist','cutebrowser.org')
        objreg.register('config', config_obj)
        assert adblock.is_whitelisted_host('qutebrowser.org') == False
        objreg.delete('config')

class TestHostBlocker :
    pass
    #testBlocker = adblock.HostBlocker()
