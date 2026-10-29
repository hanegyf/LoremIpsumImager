import hashlib, struct, argparse
from pathlib import Path
from tempfile import TemporaryDirectory

LOREM_WORDS = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in volatile velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
).split() # split into each individual word, so that we can repeat them to be 255 length (empty line as well)

while len(LOREM_WORDS) < 255: LOREM_WORDS.extend(LOREM_WORDS) # extend to at least 255 words available

MAGIC = b"WSTR" # wide bytestring as bytes object - magic header

def pack(path): # convert to a blob of bytes - this doesn't get changed from tutorial
    data = path.read_bytes()
    name = path.name.encode()
    header = MAGIC + struct.pack(">BI", len(name), len(data)) + name
    return header + data

def unpack(blob): # unpack .jpg source into bytes - unchanged from original
    if blob[:4] != MAGIC:
        raise ValueError("Not mine")
    name_len, data_len = struct.unpack(">BI", blob[4:9])
    name = blob[9 : 9 + name_len].decode()
    data = blob[9 + name_len : 9 +name_len + data_len]
    if len(data) != data_len:
        raise ValueError("the file got cut off")
    return name, data

def encode(blob, out, words=LOREM_WORDS): # encode every byte from the blob into a string of lorem ipsum words, length of string is byte value
    lines = []
    
    for byte in blob:
        text = " ".join(words[:byte]) # join with spaces to make text phrase
        lines.append(text)

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def decode(path): # decodes a .lorem file back into a raw byte blob
    blob_bytes = bytearray()

    text = Path(path).read_text(encoding="utf-8") # preserve final empty line

    for line in text.split("\n"): # split based on newline
        cleaned_line = line.strip() # remove whitespace, split by spaces

        word_count = len(cleaned_line.split()) if cleaned_line else 0 # byte is just length of line

        if word_count > 255: raise ValueError("Invalid .lorem file") # just in case

        blob_bytes.append(word_count)

    return bytes(blob_bytes)

def sha256(data): # return sha-256 hash of a byte string
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Encode JPG files into Lorem Ipsum text, decode them, or compare files")

    modes = parser.add_mutually_exclusive_group(required=True) # I hate typing these so much

    modes.add_argument("-e", "--encode", action="store_true", help="Encode one image into a .lorem file.")
    modes.add_argument("-d", "--decode", action="store_true", help="Decode one .lorem file into its original file.")
    modes.add_argument("-c", "--compare", action="store_true", help="Compare two files, or test a single file's encode/decode process.")

    parser.add_argument("files", metavar="FILE", nargs="+",type=Path,help="Input file(s): one for encode/decode, one or two for compare")
    parser.add_argument("-o", "--output", type=Path, help="Output path for encoding or decoding.")
    parser.add_argument("-w", "--word-list", type=Path, help="Optional .txt file containing words to use for encoding.")

    args = parser.parse_args()
    files = args.files

    # Check number of input files
    if (args.encode or args.decode) and len(files) != 1:
        parser.error("encode and decode require exactly one input file.")

    if args.compare and len(files) not in (1, 2):
        parser.error("compare requires one or two input files")

    if args.compare and args.output is not None:
        parser.error("--output cannot be used with --compare.")

    if args.word_list is not None and (args.decode or (args.compare and len(files) == 2)):
        parser.error("--word-list can only be used with --encode or single-file --compare.")

    try:
        # check if word list is changed
        words = LOREM_WORDS

        if args.word_list is not None:
            words = args.word_list.read_text(encoding="utf-8").split()
            if not words: parser.error("The word list must contain at least one word.")

            while len(words) < 255: words.extend(words) # make sure it's long enough

        # Encode
        if args.encode:
            source = files[0]
            output = args.output or source.with_suffix(".lorem") # either given output or make a default.lorem

            output.parent.mkdir(parents=True, exist_ok=True) # make new directory if requested
            encode(pack(source), output, words)

            print(f"Encoded: {source} -> {output}") # did you know that neovim turns -> into a nice arrow? :D
            print(f"Original SHA-256: {sha256(source.read_bytes())}")
            return 0

        # Decode
        if args.decode:
            source = files[0]
            name, data = unpack(decode(source))

            output = args.output or Path(Path(name).name)

            output.parent.mkdir(parents=True, exist_ok=True) # make new directory if needed
            output.write_bytes(data)

            print(f"Decoded: {source} -> {output}")
            print(f"Recovered SHA-256: {sha256(data)}")
            return 0

        # Compare 2 files
        if len(files) == 2:
            first, second = files
            data1 = first.read_bytes()
            data2 = second.read_bytes()

            hash1 = sha256(data1)
            hash2 = sha256(data2)
            identical = data1 == data2
            
            print(f"{first} SHA-256: {hash1}")
            print(f"{second} SHA-256: {hash2}")
            print(f"Result: {'IDENTICAL' if identical else 'DIFFERENT'}")

            return 0 if identical else 1

        # Compare 1 file, go through everything
        source = files[0]
        original_data = source.read_bytes()
        original_hash = sha256(original_data)

        with TemporaryDirectory() as temp_dir: # make temp dir so no leftover .lorem
            lorem_path = Path(temp_dir) / source.with_suffix(".lorem").name

            encode(pack(source), lorem_path, words)
            name, recovered_data = unpack(decode(lorem_path))

        recovered_hash = sha256(recovered_data)
        identical = original_data == recovered_data

        print(f"Original file: {source}")
        print(f"Recovered filename: {name}")
        print(f"Original SHA-256: {original_hash}")
        print(f"Recovered SHA-256: {recovered_hash}")
        print(f"Result: {'SUCCESSFUL' if identical else 'FAILED'}")

        return 0 if identical else 1

    except (OSError, ValueError, UnicodeError, struct.error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
