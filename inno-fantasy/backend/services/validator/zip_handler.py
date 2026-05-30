""" To unzip file and manage the temp states """
import tempfile, pathlib

class ZipHandler:
    
    def __init__(self):
        self._base = pathlib.Path(tempfile.mkdtemp())
        self._zip_file=None #temp??


    def _unzip_file(self, file)->object:
        #unzip the file to analyze
        pass
    
    def _valid_zip(self, file)->bool:
        if not self._zip_file:
            return False
        #validate zip not corrupted
        return True

    def handle_uploaded_zip(self, file)->str:
        self._valid_zip(file)
        raw_content = self._unzip_file(file)
        #stores on temp and handles the directory
        #not sure if returns id or route
        return "job_store_id_1234"