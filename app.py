from flask import Flask, request, render_template_string, send_file
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
import struct
import os
import shutil
import struct
import tempfile

from main import MAGIC, LOREM_WORDS, decode, encode, pack, sha256, unpack

app = Flask(__name__)

MAX_ENCODE_BYTES = 100 * 1024  # 100 KB

PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>LoremIpsumImager</title>
<style>
:root{color-scheme:light;--ink:#24211f;--muted:#716b65;--line:#d9d3cc;--paper:#fbfaf7;--panel:#fff;--accent:#80563e;--soft:#f0ebe5}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header,main,footer{max-width:940px;margin:auto;padding-left:24px;padding-right:24px}header{padding-top:44px;padding-bottom:24px;border-bottom:1px solid var(--line)}h1{font-size:clamp(2rem,5vw,3rem);letter-spacing:-.045em;line-height:1.05;margin:0 0 12px;font-weight:720}header p{max-width:650px;color:var(--muted);margin:0}main{padding-top:28px;padding-bottom:44px}.intro{font-size:.92rem;color:var(--muted);margin:0 0 24px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.panel{background:var(--panel);border:1px solid var(--line);padding:22px;border-radius:8px;min-width:0}.panel.wide{grid-column:1/-1}h2{font-size:1.15rem;letter-spacing:-.02em;margin:0 0 5px} .desc{font-size:.9rem;color:var(--muted);margin:0 0 18px}label{display:block;font-weight:620;font-size:.88rem;margin:14px 0 6px}input[type=file]{display:block;width:100%;font:inherit;font-size:.85rem;padding:10px;border:1px solid var(--line);border-radius:5px;background:#fff}button{margin-top:18px;background:var(--ink);color:#fff;border:0;border-radius:5px;padding:10px 15px;font:inherit;font-weight:620;cursor:pointer}button:hover{background:var(--accent)}.result{padding:13px 15px;border-left:3px solid var(--accent);background:var(--soft);margin:20px 0;overflow-wrap:anywhere}.result.error{border-color:#a33}.result p{margin:4px 0}.hash{font-family:ui-monospace,SFMono-Regular,monospace;font-size:.82rem;overflow-wrap:anywhere}.muted{color:var(--muted)}footer{border-top:1px solid var(--line);padding-top:16px;padding-bottom:32px;color:var(--muted);font-size:.82rem}a{color:var(--accent)}@media(max-width:680px){.grid{grid-template-columns:1fr}.panel.wide{grid-column:auto}header{padding-top:30px}}
</style></head><body>
<header><h1>LoremIpsumImager</h1><p>Turn a file into Lorem Ipsum text, or decode it.</p></header>
<main><p class="intro">Choose a tool below. Encoded files can become much larger than the original.</p>
{% if message %}<div class="result {% if error %}error{% endif %}"><strong>{{ message }}</strong>{% for line in details %}<p>{{ line }}</p>{% endfor %}</div>{% endif %}
<div class="grid">
<section class="panel"><h2>Encode</h2><p class="desc">Create a .lorem text file from an uploaded file.</p><form action="/encode" method="post" enctype="multipart/form-data"><label for="source">File to encode</label><input id="source" type="file" name="source" required><label for="words">Custom word list (optional)</label><input id="words" type="file" name="words" accept=".txt,text/plain"><button type="submit">Encode file</button></form></section>
<section class="panel"><h2>Decode</h2><p class="desc">Restore the original file from a .lorem file.</p><form action="/decode" method="post" enctype="multipart/form-data"><label for="lorem">.lorem file</label><input id="lorem" type="file" name="source" required><button type="submit">Decode file</button></form></section>
<section class="panel wide"><h2>Compare / verify</h2><p class="desc">Compare two files byte-for-byte, or test one file through the full encode/decode process.</p><form action="/compare" method="post" enctype="multipart/form-data"><label for="first">First file (or file to test)</label><input id="first" type="file" name="first" required><label for="second">Second file (optional; leave blank for round-trip test)</label><input id="second" type="file" name="second"><label for="compare_words">Custom word list for round-trip test (optional)</label><input id="compare_words" type="file" name="words" accept=".txt,text/plain"><button type="submit">Compare / verify</button></form></section>
</div></main><footer>Open-source project · <a href="https://github.com/hanegyf/LoremIpsumImager">Source on GitHub</a></footer></body></html>'''


def read_words(upload):
    if upload is None or not upload.filename:
        return LOREM_WORDS
    words = upload.read().decode("utf-8").split()
    if not words:
        raise ValueError("The custom word list is empty.")
    while len(words) < 255:
        words.extend(words[:])
    return words


def page(message=None, details=(), error=False, status=200):
    return render_template_string(PAGE, message=message, details=details, error=error), status


def safe_name(name, fallback="file.bin"):
    return Path(name or fallback).name or fallback


def encode_file_streaming(source_path, output_path, words):
    name = source_path.name.encode("utf-8")
    size = source_path.stat().st_size

    if len(name) > 255:
        raise ValueError("Filename is too long.")

    header = MAGIC + struct.pack(">BI", len(name), size) + name

    with output_path.open("w", encoding="utf-8", newline="") as out:
        first_line = True

        def write_bytes(data):
            nonlocal first_line
            for value in data:
                if not first_line:
                    out.write("\n")
                if value:
                    out.write(" ".join(words[:value]))
                first_line = False

        write_bytes(header)

        with source_path.open("rb") as source:
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                write_bytes(chunk)


@app.get("/")
def index():
    return page()


@app.post("/encode")
def encode_route():
    source = request.files.get("source")

    if not source or not source.filename:
        return page("Choose a file to encode.", error=True, status=400)

    source.stream.seek(0, os.SEEK_END)
    size = source.stream.tell()
    source.stream.seek(0)

    if size > MAX_ENCODE_BYTES:
        return page(
            "File is too large for the free demo",
            [
                f"Your file is {size:,} bytes. The limit is "
                f"{MAX_ENCODE_BYTES:,} bytes (100 KB).",
                "The encoding expands every byte into a line of text. "
                "Use the command-line version for larger files."
            ],
            error=True,
            status=413
        )

    directory = tempfile.mkdtemp(prefix="lorem-encode-")

    try:
        words = read_words(request.files.get("words"))
        source_path = Path(directory) / safe_name(source.filename)
        output_path = Path(directory) / (source_path.stem + ".lorem")
        source.save(source_path)

        encode_file_streaming(source_path, output_path, words)

        response = send_file(
            output_path,
            as_attachment=True,
            download_name=output_path.name,
            mimetype="text/plain; charset=utf-8"
        )

        response.call_on_close(
            lambda: shutil.rmtree(directory, ignore_errors=True)
        )
        return response

    except (OSError, ValueError, UnicodeError, struct.error) as exc:
        shutil.rmtree(directory, ignore_errors=True)
        return page("Encoding failed", [str(exc)], error=True, status=400)


@app.post("/decode")
def decode_route():
    source = request.files.get("source")
    if not source or not source.filename:
        return page("Choose a .lorem file to decode.", error=True, status=400)
    try:
        with TemporaryDirectory() as td:
            path = Path(td) / safe_name(source.filename, "upload.lorem")
            source.save(path)
            name, data = unpack(decode(path))
        return send_file(BytesIO(data), as_attachment=True, download_name=safe_name(name),
                         mimetype="application/octet-stream")
    except (OSError, ValueError, UnicodeError, struct.error) as exc:
        return page("Decoding failed", [str(exc)], error=True, status=400)


@app.post("/compare")
def compare_route():
    first = request.files.get("first")
    second = request.files.get("second")
    if not first or not first.filename:
        return page("Choose a file to compare or test.", error=True, status=400)
    try:
        first_data = first.read()
        if second and second.filename:
            second_data = second.read()
            identical = first_data == second_data
            return page("IDENTICAL" if identical else "DIFFERENT", [
                f"{safe_name(first.filename)} — {len(first_data):,} bytes",
                f"SHA-256: {sha256(first_data)}",
                f"{safe_name(second.filename)} — {len(second_data):,} bytes",
                f"SHA-256: {sha256(second_data)}",
                "Files match byte-for-byte." if identical else "Files differ byte-for-byte."
            ], error=not identical)

        words = read_words(request.files.get("words"))
        with TemporaryDirectory() as td:
            source_path = Path(td) / safe_name(first.filename)
            lorem_path = Path(td) / (source_path.stem + ".lorem")
            source_path.write_bytes(first_data)
            encode(pack(source_path), lorem_path, words)
            encoded_size = lorem_path.stat().st_size
            recovered_name, recovered = unpack(decode(lorem_path))
        identical = first_data == recovered
        return page("ROUND TRIP SUCCESSFUL" if identical else "ROUND TRIP FAILED", [
            f"Original: {len(first_data):,} bytes",
            f"Encoded text: {encoded_size:,} bytes",
            f"Original SHA-256: {sha256(first_data)}",
            f"Recovered SHA-256: {sha256(recovered)}",
            f"Recovered filename: {safe_name(recovered_name)}",
            "Recovered bytes match the original." if identical else "Recovered bytes differ from the original."
        ], error=not identical)
    except (OSError, ValueError, UnicodeError, struct.error) as exc:
        return page("Comparison failed", [str(exc)], error=True, status=400)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port= int(__import__("os").environ.get("PORT", "5000")))
