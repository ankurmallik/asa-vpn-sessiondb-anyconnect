import pandas as pd
import os

def collect_in_excel(tab_name, data, file_path):
    """
    The output_to_excel() function saves information to a Microsoft Excel file.
    ARGS:
        tab_name (String): Current date and time used to create the tab name and the table
        name in the spreadsheet.
        data (List): The data saved to a spreadsheet.
        file_path (String): The path to the spreadsheet.
    """
    # Concatenate all dictionaries in one dataframe
    df = pd.concat([pd.DataFrame(device) for device in data])

    # Check if the file already exists
    if os.path.isfile(file_path):
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='a') as writer:
            df.to_excel(writer, sheet_name=tab_name, index=False)
    else:
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='w') as writer:
            df.to_excel(writer, sheet_name=tab_name, index=False)
