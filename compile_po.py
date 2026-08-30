import sys
import struct
import re
import gettext

def po_to_dict(po_path):
    catalog = {}
    with open(po_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Match msgid and msgstr pairs
    # Handles multi-line strings
    entries = re.findall(r'(?:^|\n)msgid\s+(".*?"(?:\s*\n\s*".*?")*)\s*\nmsgstr\s+(".*?"(?:\s*\n\s*".*?")*)', content, re.MULTILINE)
    
    def parse_str(s):
        lines = re.findall(r'"((?:\\.|[^"\\])*)"', s)
        joined = "".join(lines)
        return joined.encode('raw_unicode_escape').decode('unicode_escape')

    for msgid_raw, msgstr_raw in entries:
        msgid = parse_str(msgid_raw)
        msgstr = parse_str(msgstr_raw)
        catalog[msgid] = msgstr
    return catalog

def dict_to_mo(catalog, mo_path):
    keys = sorted(catalog.keys())
    # Generate binary MO file according to GNU gettext specifications
    # Header format:
    # magic: 0x950412de
    # revision: 0
    # num_strings: N
    # orig_table_offset: 28
    # trans_table_offset: 28 + N * 8
    # hash_table_size: 0
    # hash_table_offset: 0
    
    num_strings = len(keys)
    orig_table_offset = 28
    trans_table_offset = orig_table_offset + num_strings * 8
    strings_offset = trans_table_offset + num_strings * 8

    orig_data = bytearray()
    trans_data = bytearray()

    orig_table = []
    trans_table = []

    # Pack strings
    curr_orig_pos = 0
    for k in keys:
        b_k = k.encode('utf-8') + b'\x00'
        orig_table.append((len(b_k) - 1, curr_orig_pos))
        orig_data.extend(b_k)
        curr_orig_pos += len(b_k)

    curr_trans_pos = 0
    for k in keys:
        v = catalog[k]
        b_v = v.encode('utf-8') + b'\x00'
        trans_table.append((len(b_v) - 1, curr_trans_pos))
        trans_data.extend(b_v)
        curr_trans_pos += len(b_v)

    # Now calculate absolute offsets for orig and trans tables
    strings_start = strings_offset
    orig_strings_start = strings_start
    trans_strings_start = orig_strings_start + len(orig_data)

    header = struct.pack(
        '<Iiiiiii',
        0x950412de, # magic
        0,          # revision
        num_strings,
        orig_table_offset,
        trans_table_offset,
        0,          # hash table size
        0           # hash table offset
    )

    orig_index = bytearray()
    for length, rel_offset in orig_table:
        orig_index.extend(struct.pack('<ii', length, orig_strings_start + rel_offset))

    trans_index = bytearray()
    for length, rel_offset in trans_table:
        trans_index.extend(struct.pack('<ii', length, trans_strings_start + rel_offset))

    with open(mo_path, 'wb') as f:
        f.write(header)
        f.write(orig_index)
        f.write(trans_index)
        f.write(orig_data)
        f.write(trans_data)

if __name__ == '__main__':
    print("Testing parser and compiler...")
