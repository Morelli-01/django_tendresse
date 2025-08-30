import json
import re
import codecs

def parse_and_transform_sql(input_file_path, output_file_path):
    """
    Parses an SQL dump file to extract data from the old 'Bolle_bolla' table,
    transforms it, and generates INSERT statements for the new 'core_slip' table.

    Args:
        input_file_path (str): The path to the old SQL dump file.
        output_file_path (str): The path where the new SQL file will be saved.
    """
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: The file {input_file_path} was not found.")
        return

    insert_pattern = re.compile(r"INSERT INTO `Bolle_bolla` VALUES\s*(.*?);", re.S)
    
    row_pattern = re.compile(
        r"\(" +
        r"(\d+)," +
        r"'((?:[^']|'')*)'," +
        r"'((?:[^']|'')*)'," +
        r"'((?:[^']|'')*)'," +
        r"'((?:[^']|'')*)'," +
        r"'((?:[^']|'')*)'," +
        r"'((?:[^']|'')*)'," +
        r"'((?:[^']|'')*)'," +
        r"'((?:[^']|'')*)'," +
        r"'((?:[^']|'')*)'," +
        r"(\d+)," +
        r"(\d+)," +
        r"(\d+)," +
        r"(\d+)," +
        r"(NULL|\d+)" +
        r"\)"
    )

    all_insert_blocks = insert_pattern.findall(content)

    with open(output_file_path, 'w', encoding='utf-8') as f_out:
        f_out.write("LOCK TABLES `core_slip` WRITE;\n")
        f_out.write("/*!40000 ALTER TABLE `core_slip` DISABLE KEYS */;\n")

        total_rows_processed = 0
        total_rows_found = 0
        for block in all_insert_blocks:
            rows = list(row_pattern.finditer(block))
            total_rows_found += len(rows)

            for match in rows:
                id_old = "unknown"
                try:
                    # --- 1. Extract and clean data ---
                    raw_groups = [group or '' for group in match.groups()]
                    id_old = raw_groups[0]
                    
                    cleaned_groups = [g.replace("''", "'") for g in raw_groups]
                    
                    (_, data, descrizioni_json_str, qta_json_str, um_json_str, note_json_str, 
                     lavorazione, resp_spedizione, data_trasp, aspetto, 
                     _, slip_number_old, slip_year, dst_id, _) = cleaned_groups

                    # --- 2. Data Transformation ---
                    slip_number = f"{slip_number_old}"
                    full_slip_number = f"{slip_number_old}-{slip_year}"

                    # --- KEY FIX: Unescape the JSON strings before parsing ---
                    descrizioni = json.loads(codecs.decode(descrizioni_json_str, 'unicode_escape')).get('descrizioni', [])
                    quantities = json.loads(codecs.decode(qta_json_str, 'unicode_escape')).get('qta', [])
                    units = json.loads(codecs.decode(um_json_str, 'unicode_escape')).get('um', [])
                    notes = json.loads(codecs.decode(note_json_str, 'unicode_escape')).get('note', [])
                    
                    items = []
                    for i in range(len(descrizioni)):
                        item = {
                            "description": descrizioni[i],
                            "quantity": quantities[i] if i < len(quantities) else "",
                            "unit": units[i] if i < len(units) else "",
                            "note": notes[i] if i < len(notes) else ""
                        }
                        items.append(item)
                    
                    items_json_for_sql = json.dumps(items, ensure_ascii=False).replace("'", "''")
                    recipient_id = dst_id
                    
                    # --- 3. Construct the new INSERT statement ---
                    new_insert_statement = (
                        f"INSERT INTO `core_slip` (`slip_number`, `date`, `items`, `notes`, `created_by_id`, "
                        f"`recipient_id`, `aspetto`, `data_trasp`, `lavorazione`, `resp_spedizione`, "
                        f"`full_slip_number`, `slip_year`) VALUES "
                        f"('{slip_number}', '{data}', '{items_json_for_sql}', '', 1, {recipient_id}, "
                        f"'{aspetto.replace('\'', '\\\'')}', '{data_trasp}', '{lavorazione.replace('\'', '\\\'')}', "
                        f"'{resp_spedizione.replace('\'', '\\\'')}', '{full_slip_number}', {slip_year});\n"
                    )

                    f_out.write(new_insert_statement)
                    total_rows_processed += 1

                except Exception as e:
                    print(f"Warning: Could not parse row with old id={id_old}. Error: {e}")
        
        f_out.write("/*!40000 ALTER TABLE `core_slip` ENABLE KEYS */;\n")
        f_out.write("UNLOCK TABLES;\n")

    print(f"\nScript finished.")
    print(f"Found {total_rows_found} rows in the input file.")
    print(f"Successfully processed and wrote {total_rows_processed} rows to the output file.")
    if total_rows_found != total_rows_processed:
        print(f"Skipped {total_rows_found - total_rows_processed} rows due to errors.")
    print(f"The new SQL file has been saved as: {output_file_path}")

# --- Execution ---
parse_and_transform_sql('old_bolle.sql', 'new_slips.sql')