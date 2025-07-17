import re
import json
import click
import socket
import traceback
from typing import Iterator
from libasvat.data import DataCache
from libasvat.utils import Table
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


class Cell:
    """Represents a editable cell from a Row in a Google Sheet."""

    def __init__(self, parent: 'Row', index: int, value: str):
        self.parent = parent
        self.index = index
        self._value = value
        self.original_value = self.value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        if v is None:
            self._value = ""
        elif isinstance(v, bool):
            self._value = "TRUE" if v else "FALSE"
        else:
            # TODO: como determinar que recebeu um float que deve ser formatado com `N%` na cell? Tratamos isso no as_float()
            self._value = str(v)

    def get_letter_index(self):
        """Gets the A1 notation key of this cell, uniquely identifying it in our sheet."""
        # using index+1 here since in Python indexes start from 0, but in sheets (for this letter notation), they start from 1.
        letter = columnToLetter(self.index + 1)
        return f"{letter}{self.parent.index + 1}"

    def was_changed(self):
        """Checks if this cell was changed"""
        return self._value != self.original_value

    def save_changes(self):
        """Saves changes made in this cell"""
        self.original_value = self._value

    def as_str(self):
        """Gets this cell's value as a string. Returns None if value is invalid (like an empty string)."""
        if self.value is None or self.value == "":
            return None
        return str(self.value)

    def as_int(self):
        """Gets this cell's value as an integer. Returns None if value is not a valid int."""
        try:
            return int(self.value)
        except Exception:
            return None

    def as_float(self):
        """Gets this cell's value as a float. Returns None if value is not a valid number.

        If the cell's value is a percent-value (format `X%`, where X is a number), then this
        will return `X / 100` to convert the percent to a proper numeric value.
        """
        try:
            if re.match(r"^[\d.]+[%]$", self.value):
                return float(self.value.replace("%", "")) / 100.0
            return float(self.value)
        except Exception:
            return None

    def as_bool(self):
        """Gets this cell's value as a boolean."""
        return self.value.lower() == "true"

    def as_list(self, delimiter=",") -> list[str]:
        """Gets this cell's value as a list of strings.

        The cell's value (as a str) is split using the given DELIMITER. Each item is stripped of
        leading and trailing whitespace to be returned in the list.
        If value is invalid (can't be split into a list), a empty list will be returned.
        """
        val = self.as_str()
        if val is None:
            return []
        return [v.strip() for v in val.split(delimiter)]

    def __eq__(self, other):
        if isinstance(other, Cell):
            return self.index == other.index and self.value == other.value
        elif isinstance(other, str):
            return self.value == other
        return False

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f"{self.parent}.Cell#{self.index} ({self.get_letter_index()})"

    def __hash__(self):
        return hash(self.value)


class Row:
    """Represents a editable row in a Google Sheet."""

    def __init__(self, parent: 'Sheet', index: int, cells):
        self.parent = parent
        self.index = index
        self.cells: list[Cell] = [Cell(self, i, value) for i, value in enumerate(cells)]

    def is_header(self):
        """Checks if this row is a header row"""
        return self.parent.header == self

    def as_dict(self):
        """Returns a dict representation of this row.

        Each key:value pair matches a cell. The key is the cell's value in the header row (same column), and the value is the actual cell's value.
        """
        key_indexes = self.parent.get_header_indexes()
        data: dict[str, str] = {}
        for key, i in key_indexes.items():
            data[key] = self[i].value
        return data

    def erase(self):
        """Erases this row, setting the value of all our cells to `None`.

        This is essentially deleting the row, since it'll become a blank row.

        Note that this does NOT save the changes to the row/sheet! Do that yourself by calling
        the parent's Sheet `save()` method.
        """
        for cell in self.cells:
            cell.value = None
        # TODO: actual deletion of the row?

    def __getitem__(self, key) -> Cell:
        if isinstance(key, int):
            # return cell by index
            self._extend_cells_to_index(key)
            return self.cells[key]
        elif isinstance(key, str):
            # return cell by key
            key_indexes = self.parent.get_header_indexes()
            if key not in key_indexes:
                raise KeyError(f"invalid cell key '{key}'")
            index = key_indexes[key]
            self._extend_cells_to_index(index)
            return self[index]
        # TODO: implement slice support and failsafes
        raise KeyError(f"invalid cell index/key '{key}' (a {type(key)} value)")

    def __setitem__(self, key, value):
        self[key].value = value

    def __contains__(self, key):
        if isinstance(key, int):
            return True
        elif isinstance(key, str):
            key_indexes = self.parent.get_header_indexes()
            return key in key_indexes
        return False

    def _extend_cells_to_index(self, index):
        """Extends this row's cells up to the given index (inclusive)"""
        if index >= len(self.cells):
            for i in range(len(self.cells), index + 1):
                self.cells.append(Cell(self, i, None))

    def __iter__(self) -> Iterator[Cell]:
        return iter(self.cells)

    def __len__(self):
        return len(self.cells)

    def __eq__(self, other):
        if isinstance(other, Row):
            return self.parent == other.parent and self.index == other.index and self.cells == other.cells
        return False

    def __str__(self):
        return f"{self.parent}.Row#{self.index+1}"


class Sheet:
    """Creates a Sheet object with methods to facilitate working with Google Spreadsheets.

    Notes on terminology:
    * Google Sheets API uses the term `spreadsheet` to refer to the actual file that may contain one or more
    tables, each table being a "tab" on the file, with its own title. These tables or tabs are then called `sheet` by the API.
    So a `spreadsheet` is a collection of `sheet`s.
    * In here, we use the term `sheet` more generically, both to mean the "file" (the `spreadsheet` in Google's term) and the
    "table" (the `sheet` in Google's term). At the moment, documentation for attributes/methods/etc should specify exactly
    what `sheet` means in that context (the file or the table). This ammbiguity should remain until we refactor this module.

    This Sheet class represents a single table (`sheet`) in a spreadsheet (file). To identify the sheet, we use the (spread)sheet ID
    and the table's name.
    """

    _service_obj: discovery.Resource = None
    """The Google Sheets API service object. This object is initialized once by a Sheet, and reused for all other Sheets
    to improve loading times."""

    _default_creds: 'SheetCredentials' = None
    """Default SheetCredentials object to use for authenticating Sheet API requests."""

    def __init__(self, sheet_id: str, sheet_name: str, creds: 'SheetCredentials' = None, verbose=False):
        """
        Args:
            sheet_id (str): sheet hash code. Usually found in URL.
            sheet_name (str): the individual table name from the sheet to load.
            creds (SheetCredentials, optional): the SheetCredentials object to use for authenticating access to this Sheet.
                This can be None if the Sheet's API ServiceObject is already loaded. If None, we'll try to use the default
                credentials (see ``Sheet.set_default_credentials()``).
            verbose (bool, optional): enable verbose logging.
        """
        self.sheet_id = sheet_id
        """The ID of the spreadsheet. This identifies the sheet "file" in Google Drive, and the file can have multiple sheets (tabs),
        identified by their name (see ``sheet_name``) or more rarely, their ID."""
        self.sheet_name = sheet_name
        self._table_id: int = None
        self.rows: list[Row] = []
        """The list of rows of this sheet. Each row itself is a list of Cells, ordered from first column to last."""
        self.header: Row = Row(self, -1, [])
        self._header_indexes: dict[str, int] = None
        """This is the header row."""
        self.verbose = verbose
        self._is_loaded = False
        self._credentials = creds

    def set_header_row(self, header_index):
        """Define a row to be used for keying other rows"""
        self.header = self.rows[header_index]
        self._header_indexes = None

    def get_header_indexes(self):
        """Gets a table of {column key -> column index}, based on the cells of the header row.
        This is used to index by a str key the cells of all rows besides the header."""
        if self._header_indexes is None:
            self._header_indexes = {cell.value: index for index, cell in enumerate(self.header)}
        return self._header_indexes

    def get_rows(self):
        """Return all rows that exist after the header index."""
        return self.rows[self.header.index + 1:]

    def get_row(self, index) -> Row | None:
        """Gets the Row with the given relative INDEX to the header-row.
        Returns None if the index is out-of-bounds.
        """
        actual_index = self.header.index + index + 1
        if 0 <= actual_index < len(self.rows):
            return self.rows[actual_index]

    def add_new_row(self):
        """Adds a new empty row to the end of the sheet."""
        row = Row(self, len(self.rows), [])
        self.rows.append(row)
        return row

    def get_cell(self, key: str):
        """Gets the cell by its KEY - its A1 notation index."""
        # TODO: allow key ranges as in sheets to return a list of cells?
        values = re.match(r"^([a-zA-Z]+)(\d+)$", key)
        if not values:
            raise KeyError(f"Given key '{key}' is not in A1 notation")
        column_letter = values.group(1)
        # remember A1 key indexes start from 1, and we use from 0 here.
        row_index = int(values.group(2)) - 1
        if row_index >= len(self.rows):
            raise IndexError(f"Row index from A1 key '{key}' is invalid")
        row = self.rows[row_index]
        cell_index = letterToColumn(column_letter) - 1
        return row[cell_index]

    def __getitem__(self, key: str):
        return self.get_cell(key)

    def __setitem__(self, key, value):
        cell = self[key]
        cell.value = value

    def __iter__(self) -> Iterator[Row]:
        return iter(self.get_rows())

    def get_size(self):
        """Gets the number of rows that exist after the header row."""
        return len(self.get_rows())

    @property
    def _service(self):
        """Internal authenticated google Resource object to access the Sheets API."""
        if self._credentials:
            return self._credentials.get_service()
        return self._default_creds.get_service()

    @property
    def is_loaded(self):
        """Checks if this sheet is already loaded."""
        return self._is_loaded

    def load(self):
        """Loads the sheet data from this object, using our credentials for authentication.
        Returns a boolean indicating if loading was successfull or not."""
        retry = 0
        max_retries = 3

        self._log(f"Downloading sheet '{self.sheet_name}'")

        while retry <= max_retries:
            try:
                ranges = [f"'{self.sheet_name}'!A1:ZZ"]

                result = self._service.spreadsheets().values().batchGet(spreadsheetId=self.sheet_id, ranges=ranges).execute()
                for index, row_data in enumerate(result["valueRanges"][0].get('values', [])):
                    self.rows.append(Row(self, index, row_data))
                self.set_header_row(0)
                self._is_loaded = True
                return True
            except socket.timeout:
                if retry <= max_retries:
                    retry += 1
                    self._log(f"Retry {retry} of {max_retries}.", fg="yellow")

            except HttpError:
                self._log(f"No sheet found for '{self.sheet_name}': {traceback.format_exc()}", fg="red", ignore_verbose=True)
                return False
        self._log("Requests timed out, couldn't fetch spreadsheet.", fg="red", ignore_verbose=True)
        return False

    def save(self):
        """Checks all of our cells which had their values changed and saves these changes into the remote sheet."""
        try:
            body = {
                "valueInputOption": "RAW",
                "data": []
            }
            for row in self.rows:
                for cell in row:
                    if cell.was_changed():
                        # NOTE: we're saving by specifying each modified cell as its own range to save in the command.
                        # Since the API allows to save ranges of cells in a single go, this might not be the most efficient method...
                        body["data"].append({
                            "range": f"'{self.sheet_name}'!{cell.get_letter_index()}",
                            "values": [[cell.value]]  # yes, double-list here
                            # values is a list of list of values (so rows of cells) of the values changed in this range.
                            # since we are altering cell-by-cell, its a simple double list with the value.
                        })
                        cell.save_changes()

            num_changes = len(body["data"])
            if num_changes > 0:
                self._service.spreadsheets().values().batchUpdate(spreadsheetId=self.sheet_id, body=body).execute()
                self._log(f"Sheet '{self.sheet_name}': saved changes in {num_changes} cells", fg="green")
            else:
                self._log(f"Sheet '{self.sheet_name}': no changes to save", fg="green")
            return True
        except HttpError:
            self._log(f"Couldn't write to sheet '{self.sheet_name}': {traceback.format_exc()}", fg="red", ignore_verbose=True)
            return False

    def duplicate(self, target_sheet_id: str):
        """Duplicates this sheet to the target spreadsheet.

        The duplicated sheet will be a new sheet (table) at the target spreadsheet. It is a perfect copy: all cell
        values, formatting, validation rules, etc, are copied. The sheet's name is the same name as this source
        sheet, but with a `Copy of` prefix.

        Note however that only sheet-level data is copied, since we're copying a sheet. Spreadsheet-level data, such
        as user access permissions, are not copied. The auth credentials used to access this sheet also need access
        to the target spreadsheet in order to duplicate this sheet there.

        Implementation wise, this uses the `copyTo` command from the API, which can be directly used as `Copy to >`
        in the browser's Google Sheets editor.

        Args:
            target_sheet_id (str): Target spreadsheet ID to copy this sheet to. This can be the same sheet-ID as
                this sheet, in order to duplicate it in the same spreadsheet.

        Returns:
            Sheet: a new Sheet object representing the duplicated sheet, if successful, None otherwise (error
            messages are automatically printed to the terminal).
        """
        # TODO: se target_sheet_id for igual a nossa ID, podemos usar o batchUpdate()/duplicate, que é mais simples e permite
        #   setar o nome da nova sheet diretamente
        spreadsheets = self._service.spreadsheets()
        body = {
            "destinationSpreadsheetId": target_sheet_id
        }
        try:
            response = spreadsheets.sheets().copyTo(spreadsheetId=self.sheet_id, sheetId=self.get_table_id(), body=body).execute()
            # copyTo() response is essentially the "sheet properties" dict that is also used in few other requests.
        except:
            self._log(f"{self}: failed to duplicate sheet to '{target_sheet_id}': {traceback.format_exc()}", fg="red", ignore_verbose=True)
            return
        response = Table(**response)
        dup_sheet = Sheet(target_sheet_id, response.title, self._credentials, self.verbose)
        dup_sheet._table_id = response.sheetId
        return dup_sheet

    def get_table_id(self):
        """Gets the table (sheet) ID of this sheet.

        While ``self.sheet_id`` actually refers to our *spreadsheet* ID, this table ID is our actual *sheet* ID.
        It is a simple integer ID (instead of the long string alphanumeric spreadsheet ID) that uniquely identifies
        this sheet within its spreadsheet.

        Usually the sheet's name is used to identify it in the spreadsheet, however the name can be changed (see
        ``self.rename()``). The sheet (table) ID is set automatically by Google Sheets and can never be changed.
        Some internal requests to the Sheets API require usage of the sheet-ID instead of its name, thus this can
        be used.

        The first time this used, a request will be made to the Sheets API in order to query our sheet-ID based on
        our sheet name. Afterwards, the ID is cached in this instance and will be reused by this method instead of
        re-doing the request. However, some methods of creating a sheet (such as duplicating it) will also set the
        sheet's ID, so the request is never needed.

        Returns:
            int: sheet ID that uniquely identifies this sheet within its spreadsheet. Returns None if we failed to
            get the ID. Error messages are automatically printed to the terminal.
        """
        if self._table_id is None:
            spreadsheets = self._service.spreadsheets()
            try:
                response = spreadsheets.get(spreadsheetId=self.sheet_id).execute()
            except:
                self._log(f"{self}: failed to get table-id: {traceback.format_exc()}", fg="red", ignore_verbose=True)
                return
            # The spreadsheets.get() JSON response doc has over 3.7k lines. Too much to document here.
            response = Table(**response)
            for sheet_data in response.sheets:
                if sheet_data.properties.title == self.sheet_name:
                    self._table_id = int(sheet_data.properties.sheetId)
                    break
        return self._table_id

    def rename(self, new_sheet_name: str):
        """Renames this sheet to the given new name.

        If another sheet exists in our spreadsheet with the `new_sheet_name`, this will fail.

        Args:
            new_sheet_name (str): new name to give to this sheet.

        Returns:
            bool: indicates if renaming was performed successfully. Error messages are automatically printed
            to the terminal.
        """
        spreadsheets = self._service.spreadsheets()
        body = {
            "includeSpreadsheetInResponse": False,
            "responseIncludeGridData": False,
            "requests": [
                {
                    "updateSheetProperties": {
                        "fields": "title",
                        "properties": {
                            "sheetId": self.get_table_id(),
                            "title": new_sheet_name
                        }
                    }
                }
            ],
        }
        # This spreadsheets.batchUpdate() doc has over 8k lines for its JSON body, and over 7k
        # lines for its JSON response. Too much to document here, so we just directly use what we need.
        # However, it can be used to update pretty much anything from each sheet or from the spreadsheet itself,
        # including: adding/deleting/duplicate sheets, setting formatting (colors, borders, etc), cell validation
        # rules, and more.
        try:
            response = spreadsheets.batchUpdate(spreadsheetId=self.sheet_id, body=body).execute()
            response = Table(**response)
        except Exception:
            self._log(f"{self}: failed to rename sheet to '{new_sheet_name}': {traceback.format_exc()}", fg="red", ignore_verbose=True)
            return False
        self.sheet_name = new_sheet_name
        return True

    @classmethod
    def set_default_credentials(cls, creds: 'SheetCredentials'):
        """Sets the default credentials used to authenticate Google Sheet API usage.
        Calling this will override any previouly set default credentials.
        """
        cls._default_creds = creds

    def _log(self, msg, fg="white", ignore_verbose=False):
        """Logs a message to the console if verbose output is enabled."""
        if self.verbose or ignore_verbose:
            click.secho(msg, fg=fg)

    def __str__(self):
        return f"Sheet[{self.sheet_name}]"


def columnToLetter(column):
    """Converts a numerical column index to its equivalent sheets column letter. So:
    * 1 => A
    * 2 => B
    * 26 => Z
    * 27 => AA
    * 29 => AC
    and so on.
    """
    temp = ''
    letter = ''
    while (column > 0):
        temp = (column - 1) % 26
        letter = chr(temp + 65) + letter
        column = int((column - temp - 1) / 26)
    return letter


def letterToColumn(letter):
    """Converts a sheets column letter to its equivalent numerical index. So:
    * A => 1
    * B => 2
    * Z => 26
    * AA => 27
    * AC => 29
    and so on.
    """
    column = 0
    length = len(letter)
    for i in range(length):
        column += (ord(letter[i]) - 64) * 26**(length - i - 1)
    return column


class SheetCredentials:
    """Abstract base class that represents the Credentials required to authenticate
    requests to the Google API.

    The basic API from this class allows to get the credentials, check their status and delete them.

    Subclasses of this should implement their actual logic for getting the credentials.
    """

    def __init__(self):
        self._service: discovery.Resource = None

    def get_credentials(self, scopes: list[str]) -> Credentials:
        """Gets the auth credentials for Google API using the given scopes."""
        raise NotImplementedError

    def check_status(self):
        """Checks the status of this Credentials object, printing to the terminal the current status."""
        raise NotImplementedError

    def cleanup(self):
        """Cleans up this Credentials object, doing any operation it needs to clean up whatever resources it
        used, such as removing locally stored data."""
        self._service = None

    def get_service(self) -> discovery.Resource:
        """Gets the Google's Resource service, used to call Sheets API commands, using these credentials.

        The authenticated service object is cached in this SheetCredentials object, so further calls to this method
        will return the cached object.
        """
        if self._service is None:
            discovery_url = "https://sheets.googleapis.com/$discovery/rest?version=v4"
            # For now use the same scopes for all sheets since its easier and there's been no need for custom scopes per-sheet.
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
            google_creds = self.get_credentials(scopes)
            self._service = discovery.build('sheets', 'v4', credentials=google_creds, discoveryServiceUrl=discovery_url, cache_discovery=False)
        return self._service


class UserLoginCredentials(SheetCredentials):
    """Cached User Login Credentials class.

    Basic/individual form of authentication for the Google API and Sheets. This asks the user for its google-account
    login in a browser window.

    The user-account is used to auth with Google API, accessing Sheets data. Its login credentials are stored locally
    with `DataCache`'s "password" system for safe storage, allowing it to be reused in later sessions without requiring
    the user to constantly re-login.

    The only required parameter/configuration for this is the path for a 'Google Client Secrets' JSON file, which is
    generated in Google's console and provides the OAUTH2 data necessary to login a user in your app.
    """

    def __init__(self, client_secrets_file_path: str):
        super().__init__()
        self._client_secrets_file_path: str = client_secrets_file_path
        self._cache_key = "google_token"

    def get_credentials(self, scopes: list[str]):
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        cache = DataCache()
        token_data = cache.get_password(self._cache_key)
        if token_data is not None:
            token = json.loads(token_data)
            creds = Credentials.from_authorized_user_info(token, scopes)
            click.secho(f"Using stored token for user account '{creds.account}', valid={creds.valid}", fg="blue")
        # If there are no (valid) credentials available, let the user log in.
        if creds is None or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                click.secho("Refreshing user account token...", fg="blue")
                creds.refresh(Request())
            else:
                click.secho("Checking Google user login...", fg="blue")
                flow = InstalledAppFlow.from_client_secrets_file(self._client_secrets_file_path, scopes)
                # NOTE: port was 0 and it worked on python 3.13
                #   but on python 3.9 it fails... Fixed it by using the method's default port value of 8080
                creds = flow.run_local_server(port=8080)
            # Save the credentials for the next run
            cache.set_password(self._cache_key, creds.to_json())
            click.secho(f"Successfully authenticated user account '{creds.account}'!", fg="bright_blue")
        return creds

    def check_status(self):
        cache = DataCache()
        token_data = cache.get_password(self._cache_key)
        if token_data is None:
            click.secho("No Google user token data stored", fg="yellow")
        else:
            click.secho("We have Google user token data stored", fg="green")

    def cleanup(self):
        cache = DataCache()
        cache.delete_password(self._cache_key)
