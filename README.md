# LoremIpsumImager
LoremIpsumImager encodes a file as Lorem Ipsum text and reconstructs the original file from that text. It can use its built-in word list or an optional custom `.txt` word list.

The project also includes SHA-256 checks and comparison modes to make sure that a file survives the encode/decode process unchanged.

Demo at: https://loremipsumimager.streamlit.app/

## How it works
The encoder first packs the original iflename and file contents into a binary blob. It then represents each byte as one line containing that number of words:
- A byte value of `0` becomes an empty line.
- A byte value of `3` becomes a line with three words.
- A byte value of `255` becomes a line with 255 words.
The decoder counts the words on each line to recover the bytes, then unpacks the original filename and contents. Because decoding depends on the number of words per line rather than the specific words used, a custom word list is not needed when decoding.

## Requirements
- Python 3.9 or newer
- No third-party Python packages needed, only standard library

## Usage
Run commands from the directory containing `main.py`. Replace `python` with `python3` if that is how Python is installed on your system.

### Show help
```
python main.py --help
```

### Encode a file
```
python main.py --encode house.jpg
```
This writes `house.lorem` alongside `house.jpg`.
Choose a destination explicitly with `-o`/`--output`:
```
python main.py -e house.jpg -o encoded/house.lorem
```
The output directory is created automatically if needed.


#### Encode with a custom word list
Create a text file containing whitespace-separated words, such as `words.txt`.
```
python main.py -e house.jpg --word-list words.txt -o custom.lorem
```
The `-w`/`--word-list` option reads words from the specified `.txt` file. if fewer than 255 words are supplied, the list is repeated until it contains 255 words.

### Decode a `.lorem` file
```
python main.py --decode house.lorem
```
By default, the recovered file is written to the current directory using the filename stored inside the encoded file. To specify another location:
```
python main.py -d house.lorem -o recovered/house.jpg
```
The output directory is created automatically if needed. Existing output files with the same name are overwritten.

### Compare two files
```
python main.py --compare house.jpg recovered/house.jpg
```
The script prints both SHA-256 hashes and reports `IDENTICAL` or `DIFFERENT`. It compares the actual bytes as well as displaying the hashes. The command exits with status `0` when the files are identical and `1` when they differ.

### Test a complete round trip
```
python main.py --compare house.jpg
```
With one input, compare mode encodes the file, decodes it, and compares the recovered bytes with the original. Temporary files are removed automatically. To use a custom vocabulary for this test:
```
python main.py -c house.jpg --word-list examples/words.txt
```
A successful test prints `SUCCESSFUL` and exits with status `0`; a failed comparison exits with status `1`.

## Command reference
| Option | Description |
| --- | --- |
| `-e`, `--encode` | Encode one input file as `.lorem` text. |
| `-d`, `--decode` | Decode one `.lorem` file into the original file. |
| `-c`, `--compare` | Compare two files, or test a one-file encode/decode round trip. |
| `-o`, `--output` | Set the output path for encoding or decoding. Not available with compare mode. |
| `-w`, `--word-list` | Use a custom word list for encoding or a single-file round-trip test. |
| `-h`, `--help` | Display command-line help. |
