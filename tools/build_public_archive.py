"""Build a de-identified, publishable copy of the local archive.

The source archive and the private image-ID mapping are read-only.  The output
directory must not exist.  Patient identifiers are replaced in paths and
structured content, image metadata are removed, and review screenshots have
their burned-in identifier header replaced with the anonymous identifier.
"""
from __future__ import print_function

import argparse
import csv
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
from collections import Counter, OrderedDict

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import SimpleITK as sitk


TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".r", ".ps1", ".yaml", ".yml", ".log",
    ".pipeline_stamp",
}
SKIP_SUFFIXES = {".pyc", ".tmp"}
DIRECT_IDENTIFIER = re.compile(
    r"^(?:name|patient_name|subject_name|mrn|medical_record(?:_number)?|"
    r"hospital_id|id_card|phone|telephone|address)$", re.I)
DIRECT_IDENTIFIER_CN = re.compile(
    r"姓名|病历号|病案号|住院号|身份证|联系电话|电话|住址|地址")
DATE_FIELD = re.compile(r"(?:^|_)(?:date|birth_date|dob)(?:$|_)", re.I)
DATE_FIELD_CN = re.compile(r"日期|出生")
ID_FIELD = re.compile(
    r"(?:^|_)(?:patient_id|subject_id|case_id|image_id|imaging_id)(?:s)?(?:$|_)",
    re.I)
ID_FIELD_CN = re.compile(r"影像号|患者编号|病例编号")
WINDOWS_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s`\"'<>|]+")
UNC_PATH = re.compile(r"(?<![\\])\\\\[^\s`\"'<>|]+")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def real(path):
    # Keep an explicitly supplied ASCII junction spelling for SimpleITK on
    # Windows.  Containment checks below still resolve junction targets.
    return os.path.abspath(path)


def canonical(path):
    return os.path.realpath(os.path.abspath(path))


def is_within(path, root):
    path = canonical(path)
    root = canonical(root)
    return path == root or path.startswith(root + os.sep)


def load_mapping(path):
    result = OrderedDict()
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"original_image_id", "anonymous_image_id"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise RuntimeError("mapping columns are invalid")
        for row in reader:
            original = str(row["original_image_id"]).strip()
            anonymous = str(row["anonymous_image_id"]).strip()
            if not original or not anonymous or original in result:
                raise RuntimeError("mapping contains a blank or duplicate identifier")
            result[original] = anonymous
    if not result:
        raise RuntimeError("mapping is empty")
    return result


class ArchiveSanitizer(object):
    def __init__(self, source, output, mapping, limit=None):
        self.source = real(source)
        self.output = real(output)
        self.mapping = mapping
        self.limit = limit
        alternatives = "|".join(
            re.escape(value) for value in sorted(mapping, key=len, reverse=True))
        self.raw_id_pattern = re.compile(
            r"(?<![0-9])(?:" + alternatives + r")(?![0-9])")
        self.unknown_ids = {}
        self.stats = Counter()
        self.destinations = set()

    def anonymous_unknown(self, value):
        value = str(value)
        if value not in self.unknown_ids:
            self.unknown_ids[value] = "SUBJ-" + secrets.token_hex(5).upper()
        return self.unknown_ids[value]

    def replace_ids(self, text):
        def repl(match):
            self.stats["identifier_replacements"] += 1
            return self.mapping[match.group(0)]
        return self.raw_id_pattern.sub(repl, text)

    def sanitize_text(self, text):
        text = self.replace_ids(text)
        text, count = WINDOWS_PATH.subn("<LOCAL_PATH>", text)
        self.stats["path_replacements"] += count
        text, count = UNC_PATH.subn("<NETWORK_PATH>", text)
        self.stats["path_replacements"] += count
        return text

    def field_kind(self, field):
        field = str(field or "").strip()
        if DIRECT_IDENTIFIER.search(field) or DIRECT_IDENTIFIER_CN.search(field):
            return "direct"
        if DATE_FIELD.search(field) or DATE_FIELD_CN.search(field):
            return "date"
        if ID_FIELD.search(field) or ID_FIELD_CN.search(field):
            return "id"
        return "other"

    def sanitize_field(self, value, field=None):
        if value is None:
            return value
        kind = self.field_kind(field)
        text = str(value)
        if kind == "direct":
            return "" if not text.strip() else "<REDACTED>"
        if kind == "date":
            return "" if not text.strip() else "<REDACTED_DATE>"
        if kind == "id":
            stripped = text.strip()
            if not stripped:
                return text
            if stripped in self.mapping:
                self.stats["identifier_replacements"] += 1
                return self.mapping[stripped]
            if stripped.startswith(("IMG-", "SUBJ-")):
                return stripped
            if re.match(r"^[0-9A-Za-z_.-]+$", stripped):
                self.stats["unknown_identifier_replacements"] += 1
                return self.anonymous_unknown(stripped)
        return self.sanitize_text(text)

    def sanitize_component(self, value):
        value = self.replace_ids(value)
        if WINDOWS_PATH.search(value) or UNC_PATH.search(value):
            raise RuntimeError("absolute path appeared in a path component")
        return value

    def destination_for(self, source_path):
        relative = os.path.relpath(source_path, self.source)
        parts = [self.sanitize_component(part) for part in relative.split(os.sep)]
        destination = os.path.join(self.output, *parts)
        if not is_within(destination, self.output):
            raise RuntimeError("destination escapes output root")
        key = os.path.normcase(destination)
        if key in self.destinations:
            raise RuntimeError("de-identification created a path collision")
        self.destinations.add(key)
        return destination

    @staticmethod
    def decode_text(data):
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                pass
        raise RuntimeError("text encoding is unsupported")

    def process_text(self, source, destination):
        with open(source, "rb") as handle:
            text = self.decode_text(handle.read())
        text = self.sanitize_text(text)
        with open(destination, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def process_csv(self, source, destination):
        with open(source, "rb") as handle:
            text = self.decode_text(handle.read())
        rows = csv.reader(text.splitlines())
        with open(destination, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            try:
                header = next(rows)
            except StopIteration:
                return
            clean_header = [self.sanitize_text(value) for value in header]
            writer.writerow(clean_header)
            for row in rows:
                cleaned = []
                for index, value in enumerate(row):
                    field = header[index] if index < len(header) else None
                    cleaned.append(self.sanitize_field(value, field))
                writer.writerow(cleaned)

    def clean_json_value(self, value, field=None):
        if isinstance(value, dict):
            result = OrderedDict()
            for key, item in value.items():
                clean_key = self.sanitize_text(str(key))
                result[clean_key] = self.clean_json_value(item, key)
            return result
        if isinstance(value, list):
            return [self.clean_json_value(item, field) for item in value]
        if isinstance(value, tuple):
            return [self.clean_json_value(item, field) for item in value]
        if isinstance(value, str):
            return self.sanitize_field(value, field)
        if isinstance(value, (int, float)) and self.field_kind(field) == "id":
            return self.sanitize_field(value, field)
        return value

    def process_json(self, source, destination):
        with open(source, "r", encoding="utf-8-sig") as handle:
            payload = json.load(handle, object_pairs_hook=OrderedDict)
        payload = self.clean_json_value(payload)
        with open(destination, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=True)
            handle.write("\n")

    def process_npz(self, source, destination):
        clean = OrderedDict()
        with np.load(source, allow_pickle=False) as payload:
            for key in payload.files:
                array = payload[key]
                kind = self.field_kind(key)
                if array.dtype.kind in ("U", "S") or kind == "id":
                    values = []
                    for item in array.reshape(-1):
                        if isinstance(item, bytes):
                            item = item.decode("utf-8")
                        values.append(self.sanitize_field(item, key))
                    clean[key] = np.asarray(values).reshape(array.shape)
                else:
                    clean[key] = array
        np.savez_compressed(destination, **clean)

    def process_nrrd(self, source, destination):
        image = sitk.ReadImage(source)
        for key in list(image.GetMetaDataKeys()):
            image.EraseMetaData(key)
        sitk.WriteImage(image, destination, True)

    def process_png(self, source, destination):
        with Image.open(source) as image:
            clean = image.copy()
        clean.info.clear()
        relative = os.path.relpath(source, self.source).replace("\\", "/")
        if relative.startswith("roi_review_cases/"):
            draw = ImageDraw.Draw(clean)
            band = min(clean.height, max(72, int(round(clean.height * 0.065))))
            if clean.mode in ("RGB", "RGBA"):
                fill = (0, 0, 0, 255) if clean.mode == "RGBA" else (0, 0, 0)
                ink = (255, 255, 255, 255) if clean.mode == "RGBA" else (255, 255, 255)
            else:
                fill = 0
                ink = 255
            draw.rectangle((0, 0, clean.width, band), fill=fill)
            stem = os.path.splitext(os.path.basename(destination))[0]
            label = stem.replace("_", " | ")
            try:
                font = ImageFont.truetype("arial.ttf", max(14, band // 3))
            except Exception:
                font = ImageFont.load_default()
            box = draw.textbbox((0, 0), label, font=font)
            width = box[2] - box[0]
            height = box[3] - box[1]
            draw.text(((clean.width - width) // 2, (band - height) // 2),
                      label, fill=ink, font=font)
            self.stats["review_headers_redrawn"] += 1
        clean.save(destination, format="PNG", optimize=True)

    def process_other(self, source, destination):
        with open(source, "rb") as handle:
            data = handle.read()
        for original in self.mapping:
            if original.encode("ascii") in data:
                raise RuntimeError("raw identifier found in unsupported binary file")
        shutil.copy2(source, destination)

    def process_file(self, source):
        suffix = os.path.splitext(source)[1].lower()
        relative_parts = os.path.relpath(source, self.source).split(os.sep)
        if suffix in SKIP_SUFFIXES or "__pycache__" in relative_parts:
            self.stats["excluded_cache_or_temp"] += 1
            return
        destination = self.destination_for(source)
        parent = os.path.dirname(destination)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        if suffix == ".csv":
            self.process_csv(source, destination)
        elif suffix == ".json":
            self.process_json(source, destination)
        elif suffix == ".npz":
            self.process_npz(source, destination)
        elif suffix == ".nrrd":
            self.process_nrrd(source, destination)
        elif suffix == ".png":
            self.process_png(source, destination)
        elif suffix in TEXT_SUFFIXES:
            self.process_text(source, destination)
        else:
            self.process_other(source, destination)
        self.stats["published_files"] += 1
        self.stats["published_bytes"] += os.path.getsize(destination)

    def run(self):
        if not os.path.isdir(self.source):
            raise RuntimeError("source archive does not exist")
        if os.path.exists(self.output):
            raise RuntimeError("output directory already exists")
        if is_within(self.output, self.source) or is_within(self.source, self.output):
            raise RuntimeError("source and output must be separate trees")
        os.makedirs(self.output)
        paths = []
        for root, directories, files in os.walk(self.source):
            directories.sort()
            files.sort()
            for name in files:
                paths.append(os.path.join(root, name))
        self.stats["source_files"] = len(paths)
        if self.limit is not None:
            paths = paths[:self.limit]
        for index, path in enumerate(paths, 1):
            self.process_file(path)
            if index % 250 == 0:
                print("processed %d/%d" % (index, len(paths)), flush=True)
        self.write_public_notes()
        self.verify()
        return dict(self.stats)

    def write_public_notes(self):
        readme = os.path.join(self.output, "PUBLIC_ARCHIVE_README.md")
        text = """# Public de-identified archive

This directory is a de-identified copy of the local project archive. Original
image identifiers were replaced with anonymous identifiers in file names and
structured content. Direct identifiers and exact date fields were redacted,
local paths were removed, NRRD and PNG metadata were stripped, and burned-in
identifier headers in ROI review screenshots were replaced. Python bytecode,
`__pycache__` directories, and empty temporary files are excluded because they
are reproducible process artifacts rather than research records.

The private identifier mapping is not included.
"""
        with open(readme, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        self.stats["published_files"] += 1
        self.stats["published_bytes"] += os.path.getsize(readme)

    def verify(self):
        failures = []
        largest = 0
        for root, directories, files in os.walk(self.output):
            directories.sort()
            files.sort()
            for name in files:
                path = os.path.join(root, name)
                relative = os.path.relpath(path, self.output)
                largest = max(largest, os.path.getsize(path))
                if self.raw_id_pattern.search(relative):
                    failures.append("identifier_in_path")
                suffix = os.path.splitext(path)[1].lower()
                if suffix in TEXT_SUFFIXES or suffix in (".csv", ".json"):
                    with open(path, "rb") as handle:
                        text = self.decode_text(handle.read())
                    if self.raw_id_pattern.search(text):
                        failures.append("identifier_in_text")
                    if WINDOWS_PATH.search(text):
                        failures.append("absolute_path_in_text")
                elif suffix == ".nrrd":
                    with open(path, "rb") as handle:
                        header = handle.read(65536).split(b"\n\n", 1)[0]
                    if self.raw_id_pattern.search(header.decode("latin1")):
                        failures.append("identifier_in_nrrd_header")
                elif suffix == ".npz":
                    with np.load(path, allow_pickle=False) as payload:
                        for key in payload.files:
                            array = payload[key]
                            if array.dtype.kind in ("U", "S"):
                                joined = "\n".join(
                                    item.decode("utf-8") if isinstance(item, bytes)
                                    else str(item) for item in array.reshape(-1))
                                if self.raw_id_pattern.search(joined):
                                    failures.append("identifier_in_npz")
                                    break
                elif suffix == ".png":
                    with Image.open(path) as image:
                        if image.info:
                            failures.append("png_metadata_present")
                if len(failures) >= 20:
                    break
            if len(failures) >= 20:
                break
        self.stats["largest_public_file_bytes"] = largest
        if largest > 100 * 1024 * 1024:
            failures.append("github_file_limit")
        if failures:
            raise RuntimeError("public archive verification failed: %s" %
                               ", ".join(sorted(set(failures))))
        manifest = OrderedDict([
            ("schema_version", "1.0"),
            ("status", "DEIDENTIFIED_FOR_PUBLICATION"),
            ("source_file_count", int(self.stats["source_files"])),
            ("published_file_count", int(self.stats["published_files"] + 1)),
            ("excluded_cache_or_temp_count",
             int(self.stats["excluded_cache_or_temp"])),
            ("identifier_replacement_count",
             int(self.stats["identifier_replacements"])),
            ("unknown_identifier_replacement_count",
             int(self.stats["unknown_identifier_replacements"])),
            ("local_path_replacement_count", int(self.stats["path_replacements"])),
            ("roi_review_headers_redrawn",
             int(self.stats["review_headers_redrawn"])),
            ("largest_file_bytes", int(largest)),
            ("private_mapping_included", False),
            ("patient_level_archive", True),
        ])
        manifest_path = os.path.join(self.output, "PUBLIC_ARCHIVE_MANIFEST.json")
        with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        self.stats["published_files"] += 1
        self.stats["published_bytes"] += os.path.getsize(manifest_path)


def main():
    args = parse_args()
    source = real(args.source)
    output = real(args.output)
    mapping_path = real(args.mapping)
    if os.path.islink(source):
        raise RuntimeError("source archive may not be a link")
    sanitizer = ArchiveSanitizer(
        source, output, load_mapping(mapping_path), limit=args.limit)
    result = sanitizer.run()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
