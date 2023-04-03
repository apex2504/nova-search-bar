import defusedxml.ElementTree as et
import os
import uuid
import shutil
import sqlite3
import zipfile

from io import BytesIO, IOBase
from xml.etree.ElementTree import Element


class BadFile(Exception):
    pass


class BetterZipFile: # Loosely based on https://github.com/twbgc/sunzip
    def __init__(self, zip_file) -> None:
        """
        `zip_file`: A file-like object representing the zip file.
        """
        self.zip_file = zipfile.ZipFile(zip_file, 'r')
        self.max_threshold = 100


    def is_zip_file(self) -> bool:
        """
        Check if the file is a valid zip.

        Returns
        ------------
        A :bool:`int` indicating whether or not the file is a valid zip.
        """
        if zipfile.is_zipfile(self.zip_file.fp):
            return True
        return False


    def is_nested(self) -> bool:
        """
        Check whether or not the zip file contains another zip within it.

        Returns
        ------------
        A :class:`bool` showing whether or not the file contains another zip inside.
        """
        for f in self.zip_file.namelist():
            if os.path.splitext(f)[1] == '.zip':
                return True
        return False


    def get_uncompressed_size(self) -> int:
        """
        Retrieve the uncompressed size of the zip file.

        Returns
        ------------
        An :class:`int` representing the uncompressed size of the zip file.
        """
        return sum(zp.file_size for zp in self.zip_file.infolist())


    def get_compressed_size(self) -> int:
        """
        Retrieve the compressed size of the zip file.

        Returns
        ------------
        An :class:`int` representing the compressed size of the zip file.
        """
        return sum(zp.compress_size for zp in self.zip_file.infolist())


    def get_compression_ratio(self) -> float:
        """
        Retrieve the compression ratio of the zip file.

        Returns
        ------------
        A :class:`float` representing the compression ratio.
        """
        try:
            cr = self.get_uncompressed_size() / self.get_compressed_size()
            return cr
        except ZeroDivisionError:
            return 0.0


def uuid4() -> str:
    return str(uuid.uuid4())


def build_new_file(uploaded_file: IOBase) -> memoryview:
    """
    Build a new Nova backup file with search bars removed.

    Parameters
    ------------
    uploaded_file: :class:`IOBase`
        The file that the user uploaded, retrieved from the server.

    Returns
    ------------
    A :class:`memoryview` containing the reconstructed Nova backup.
    """
    data = BytesIO(uploaded_file)
    data.seek(0)

    try:
        zp = BetterZipFile(data)
    except zipfile.BadZipFile:
        raise BadFile
    if any((zp.is_nested(), zp.get_compression_ratio() >= zp.max_threshold)) or not zp.is_zip_file():
        shutil.rmtree(session, ignore_errors=True)
        raise BadFile

    session = uuid4()
    os.mkdir(session)

    zp.zip_file.extractall(session)

    conn = sqlite3.connect(f'{session}/nova.db')
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM favorites
        WHERE appWidgetProvider LIKE 'com.teslacoilsw.launcher/#custom-widget-%'
        OR appWidgetProvider = 'com.google.android.googlequicksearchbox/com.google.android.googlequicksearchbox.SearchWidgetProvider\''''
    ) # Remove any Nova search bars and Google search bars from the home screen.
    conn.commit()
    conn.close()

    try:
        tree = et.parse(f'{session}/nova.xml')
        # Hopefully handle cases where the dock search bar is replaced with a custom widget.
        # Apparently this is left over from v6 but it still seems to be used.
        dock_custom_qsb = bool(next((elem for elem in tree.findall('int') if elem.attrib['name']=='dock_qsb_appwidgetid'), False))
        sb_placement = next(elem for elem in tree.findall('string') if elem.attrib['name']=='searchbar_placement') # Is this always present in backups? Hope so :mmLol:
        is_persistent = sb_placement.text in ('PERSISTENT', 'WIDGET')
        if is_persistent or not dock_custom_qsb:
            attr = next(elem for elem in tree.findall('string') if elem.attrib['name']=='searchbar_placement')
            attr.text = 'NONE'

        if attr := next((elem for elem in tree.findall('string') if elem.attrib['name']=='drawer_searchbar_position'), None):
            attr.text = 'NONE' # This item isn't always present in backups.
        else: # If it isn't, we should create it.
            elem = Element('string', {'name': 'drawer_searchbar_position'})
            elem.text = 'NONE'
            tree.getroot().append(elem)

        tree.write(f'{session}/nova.xml')

        with open(f'{session}/supportDetails.txt', 'r') as sd:
            details = sd.read()
        with open(f'{session}/supportDetails.txt', 'w') as sd:
            sd.write(f'Search bars automatically removed from backup.\n{details}')

        bt = BytesIO()
        with zipfile.ZipFile(bt, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as f:
            for item in os.listdir(session):
                f.write(f'{session}/{item}', item)

    except Exception: # This could break anywhere and it's probably because the backup file is invalid for some reason. A basic handler is probably fine.
        shutil.rmtree(session, ignore_errors=True)
        raise BadFile

    shutil.rmtree(session, ignore_errors=True)
    bt.seek(0)
    return bt.getbuffer()
