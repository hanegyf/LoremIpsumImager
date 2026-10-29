from pathlib import Path
from tempfile import TemporaryDirectory
import struct

import streamlit as st

from main import LOREM_WORDS, decode, encode, pack, sha256, unpack

MAX_SOURCE_BYTES = 20_000_000
MAX_LOREM_BYTES = 50 * 1024 * 1024

st.set_page_config(page_title="LoremIpsumImager", page_icon=None, layout="wide")
st.title("LoremIpsumImager")
st.write(
    "Encode files as Lorem Ipsum text, decode `.lorem` files, and verify that "
    "the original bytes survive a round trip. No local installation required."
)
st.info(
    "Demo limit: source files for encoding and round-trip tests must be 20 KB or smaller. "
    "Each byte expands into a line of words, so encoded files can become much larger than the original."
)


def words_from_upload(upload):
    if upload is None:
        return LOREM_WORDS
    try:
        words = upload.getvalue().decode("utf-8").split()
    except UnicodeDecodeError:
        st.error("The word-list file must be valid UTF-8 text.")
        return None
    if not words:
        st.error("The word-list file must contain at least one word.")
        return None
    while len(words) < 255:
        words.extend(words[:])
    return words


def safe_name(name, fallback="file.bin"):
    name = Path(name or fallback).name
    return name or fallback


def show_lorem_preview(data):
    lines = data.decode("utf-8").split("\n")
    preview = []
    for i, line in enumerate(lines[:6], start=1):
        visible = line[:100]
        if len(line) > 100:
            visible += "..."
        preview.append(f"{i:>3}: {visible}")
    st.caption(f"Preview: first {min(6, len(lines))} lines of {len(lines):,} total lines.")
    st.code("\n".join(preview) or "(empty file)", language="text")


def check_source_size(upload):
    if len(upload.getvalue()) > MAX_SOURCE_BYTES:
        st.error(
            f"This demo accepts source files up to {MAX_SOURCE_BYTES:,} bytes (20 KB). "
            "The text representation expands substantially."
        )
        return False
    return True


encode_tab, decode_tab, compare_tab = st.tabs(["Encode", "Decode", "Compare / Verify"])

with encode_tab:
    st.subheader("Encode a file")
    st.write("Upload a small image or other file and download its `.lorem` representation.")
    with st.form("encode_form"):
        source_upload = st.file_uploader(
            "File to encode", key="encode_source", help="For this hosted demo, use a file no larger than 20 KB."
        )
        word_upload = st.file_uploader(
            "Custom word list (optional .txt)", type=["txt"], key="encode_words"
        )
        encode_clicked = st.form_submit_button("Encode")

    if encode_clicked:
        if source_upload is None:
            st.error("Choose a file to encode.")
        elif check_source_size(source_upload):
            words = words_from_upload(word_upload)
            if words is not None:
                try:
                    with TemporaryDirectory() as temp_dir:
                        source_path = Path(temp_dir) / safe_name(source_upload.name)
                        output_path = Path(temp_dir) / f"{source_path.stem}.lorem"
                        source_path.write_bytes(source_upload.getvalue())
                        encode(pack(source_path), output_path, words)
                        lorem_data = output_path.read_bytes()
                    st.success("Encoding complete.")
                    st.write(f"Original size: {len(source_upload.getvalue()):,} bytes")
                    st.write(f"Encoded size: {len(lorem_data):,} bytes")
                    st.write(f"Original SHA-256: `{sha256(source_upload.getvalue())}`")
                    st.download_button(
                        "Download .lorem file",
                        data=lorem_data,
                        file_name=f"{Path(safe_name(source_upload.name)).stem}.lorem",
                        mime="text/plain",
                    )
                    show_lorem_preview(lorem_data)
                except (OSError, ValueError, UnicodeError, struct.error) as exc:
                    st.error(f"Encoding failed: {exc}")

with decode_tab:
    st.subheader("Decode a .lorem file")
    st.write("Upload a `.lorem` file to reconstruct and download the original file.")
    lorem_upload = st.file_uploader(".lorem file", type=["lorem", "txt"], key="decode_source")
    if lorem_upload is not None:
        lorem_data = lorem_upload.getvalue()
        if len(lorem_data) > MAX_LOREM_BYTES:
            st.error("This demo accepts .lorem files up to 50 MB.")
        elif st.button("Decode", key="decode_button"):
            try:
                with TemporaryDirectory() as temp_dir:
                    lorem_path = Path(temp_dir) / safe_name(lorem_upload.name, "upload.lorem")
                    lorem_path.write_bytes(lorem_data)
                    original_name, original_data = unpack(decode(lorem_path))
                download_name = safe_name(original_name)
                st.success("Decoding complete.")
                st.write(f"Recovered file: `{download_name}`")
                st.write(f"Recovered size: {len(original_data):,} bytes")
                st.write(f"Recovered SHA-256: `{sha256(original_data)}`")
                st.download_button(
                    "Download recovered file",
                    data=original_data,
                    file_name=download_name,
                    mime="application/octet-stream",
                )
                suffix = Path(download_name).suffix.lower()
                if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
                    st.image(original_data, caption=f"Recovered preview: {download_name}")
            except (OSError, ValueError, UnicodeError, struct.error) as exc:
                st.error(f"Decoding failed: {exc}")

with compare_tab:
    st.subheader("Compare files or verify a round trip")
    compare_mode = st.radio(
        "Choose a test", ["Compare two files", "Encode → decode → verify"], horizontal=True
    )

    if compare_mode == "Compare two files":
        with st.form("compare_files_form"):
            first_upload = st.file_uploader("First file", key="compare_first")
            second_upload = st.file_uploader("Second file", key="compare_second")
            compare_clicked = st.form_submit_button("Compare")
        if compare_clicked:
            if first_upload is None or second_upload is None:
                st.error("Upload both files to compare them.")
            else:
                first_data = first_upload.getvalue()
                second_data = second_upload.getvalue()
                identical = first_data == second_data
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**{first_upload.name}**")
                    st.write(f"Size: {len(first_data):,} bytes")
                    st.code(sha256(first_data))
                with col2:
                    st.write(f"**{second_upload.name}**")
                    st.write(f"Size: {len(second_data):,} bytes")
                    st.code(sha256(second_data))
                if identical:
                    st.success("IDENTICAL — the files have the same bytes.")
                else:
                    st.warning("DIFFERENT — the files have different bytes.")

    else:
        with st.form("roundtrip_form"):
            roundtrip_upload = st.file_uploader("File to test", key="roundtrip_source")
            roundtrip_words = st.file_uploader(
                "Custom word list (optional .txt)", type=["txt"], key="roundtrip_words"
            )
            roundtrip_clicked = st.form_submit_button("Run round-trip test")
        if roundtrip_clicked:
            if roundtrip_upload is None:
                st.error("Choose a file to test.")
            elif check_source_size(roundtrip_upload):
                words = words_from_upload(roundtrip_words)
                if words is not None:
                    original_data = roundtrip_upload.getvalue()
                    try:
                        with TemporaryDirectory() as temp_dir:
                            source_path = Path(temp_dir) / safe_name(roundtrip_upload.name)
                            lorem_path = Path(temp_dir) / f"{source_path.stem}.lorem"
                            source_path.write_bytes(original_data)
                            encode(pack(source_path), lorem_path, words)
                            recovered_name, recovered_data = unpack(decode(lorem_path))
                        original_hash = sha256(original_data)
                        recovered_hash = sha256(recovered_data)
                        st.write(f"Original SHA-256: `{original_hash}`")
                        st.write(f"Recovered SHA-256: `{recovered_hash}`")
                        st.write(f"Recovered filename: `{safe_name(recovered_name)}`")
                        if original_data == recovered_data:
                            st.success("SUCCESSFUL — the recovered file matches the original byte for byte.")
                        else:
                            st.error("FAILED — the recovered file differs from the original.")
                    except (OSError, ValueError, UnicodeError, struct.error) as exc:
                        st.error(f"Round-trip test failed: {exc}")

st.divider()
st.caption("Files are processed in temporary storage for the current session. They are not added to the project repository.")
