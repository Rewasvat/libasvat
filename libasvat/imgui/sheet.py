from imgui_bundle import imgui
import libasvat.google_sheet as google_sheet


class ImguiSheet:
    """Utility Imgui component to display a Google Sheet in imgui as a table."""

    def __init__(self, sheet: google_sheet.Sheet):
        self.sheet = sheet

    def render(self):
        """Renders this sheet as a table in imgui.

        NOTE: for now, it is strictly a read-only display.
        """
        if not self.sheet.is_loaded:
            if not self.sheet.load():
                imgui.text_colored((1, 0, 0, 1), f"Couldn't load {self.sheet}")
                return

        flags = imgui.TableFlags_.row_bg | imgui.TableFlags_.borders_h | imgui.TableFlags_.resizable
        flags |= imgui.TableFlags_.hideable | imgui.TableFlags_.sortable
        table_id = f"Table{self.sheet.sheet_name}"
        num_columns = len(self.sheet.header)
        if imgui.begin_table(table_id, num_columns, flags):
            imgui.table_setup_scroll_freeze(1, 1)
            for cell in self.sheet.header:
                imgui.table_setup_column(cell.value)

            imgui.table_headers_row()

            for row in self.sheet:
                imgui.push_id(f"table_row_{repr(row)}")
                imgui.table_next_row(0, 1)

                for cell in row:
                    imgui.table_next_column()
                    imgui.text(cell.value)

                imgui.pop_id()

            imgui.end_table()
