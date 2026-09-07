from __future__ import annotations

import gzip
import os
import stat
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

from filelock import FileLock

from vcf_api.variants.exceptions import InvalidVcfError
from vcf_api.variants.models import PageRequest, PageResult, VariantRecord


class VcfFileRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = FileLock(f"{path}.lock")

    def validate_source(self) -> None:
        if not self.path.is_file():
            raise FileNotFoundError(f"VCF file does not exist: {self.path}")
        with self._open_read() as source:
            if not any(line.startswith("#CHROM\tPOS\tID\tREF\tALT") for line in source):
                raise InvalidVcfError("VCF header with CHROM, POS, ID, REF and ALT was not found")

    def revision(self) -> str:
        return self._revision(self.path.stat())

    @staticmethod
    def _revision(metadata: os.stat_result) -> str:
        return f"{metadata.st_ino}:{metadata.st_size}:{metadata.st_mtime_ns}"

    def list(self, request: PageRequest) -> PageResult:
        start = (request.page - 1) * request.page_size
        stop = start + request.page_size
        total = 0
        items: list[VariantRecord] = []

        with self._open_read() as source:
            revision = self._revision(os.fstat(source.fileno()))
            for fields in self._records(source):
                if request.variant_id is not None and fields[2] != request.variant_id:
                    continue
                if start <= total < stop:
                    items.append(self._to_variant(fields))
                total += 1
        return PageResult(items=items, total=total, revision=revision)

    def create(self, variant: VariantRecord) -> None:
        def transform(source: TextIO, target: TextIO) -> int:
            column_count = None
            last_had_newline = True
            for line in source:
                if line.startswith("#CHROM\t"):
                    column_count = len(line.rstrip("\r\n").split("\t"))
                target.write(line)
                last_had_newline = line.endswith("\n")
            if not last_had_newline:
                target.write("\n")
            if column_count is None or column_count < 8:
                raise InvalidVcfError("VCF header must contain at least eight columns")
            values = variant.model_dump()
            target.write(
                "\t".join(str(values[name]) for name in ("chrom", "pos", "id", "ref", "alt"))
                + "\t." * (column_count - 5)
                + "\n"
            )
            return 1

        self._atomic_rewrite(transform)

    def update_by_id(self, variant_id: str, variant: VariantRecord) -> int:
        replacement = variant.model_dump()

        def transform(source: TextIO, target: TextIO) -> int:
            affected = 0
            for line in source:
                if line.startswith("#"):
                    target.write(line)
                    continue
                fields = line.rstrip("\r\n").split("\t")
                if len(fields) >= 5 and fields[2] == variant_id:
                    fields[:5] = [
                        str(replacement[name]) for name in ("chrom", "pos", "id", "ref", "alt")
                    ]
                    target.write("\t".join(fields) + "\n")
                    affected += 1
                else:
                    target.write(line)
            return affected

        return self._atomic_rewrite(transform)

    def delete_by_id(self, variant_id: str) -> int:
        def transform(source: TextIO, target: TextIO) -> int:
            affected = 0
            for line in source:
                if line.startswith("#"):
                    target.write(line)
                    continue
                fields = line.rstrip("\r\n").split("\t")
                if len(fields) >= 3 and fields[2] == variant_id:
                    affected += 1
                    continue
                target.write(line)
            return affected

        return self._atomic_rewrite(transform)

    @contextmanager
    def _open_read(self) -> Iterator[TextIO]:
        if self.path.suffix == ".gz":
            with gzip.open(self.path, mode="rt", encoding="utf-8", newline="") as source:
                yield source
        else:
            with self.path.open(mode="r", encoding="utf-8", newline="") as source:
                yield source

    @staticmethod
    def _records(source: TextIO) -> Iterator[list[str]]:
        for line_number, line in enumerate(source, start=1):
            if line.startswith("#") or not line.strip():
                continue
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) < 5:
                raise InvalidVcfError(f"Malformed VCF record at line {line_number}")
            yield fields

    @staticmethod
    def _to_variant(fields: list[str]) -> VariantRecord:
        try:
            return VariantRecord(
                chrom=fields[0],
                pos=int(fields[1]),
                id=fields[2],
                ref=fields[3],
                alt=fields[4],
            )
        except (ValueError, IndexError) as error:
            raise InvalidVcfError("Invalid values in VCF record") from error

    def _atomic_rewrite(self, transform: Callable[[TextIO, TextIO], int]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
            )
            os.close(descriptor)
            temporary_path = Path(temporary_name)
            try:
                with self._open_read() as source, self._open_write(temporary_path) as target:
                    affected = transform(source, target)
                if affected > 0:
                    current_mode = stat.S_IMODE(self.path.stat().st_mode)
                    os.chmod(temporary_path, current_mode)
                    os.replace(temporary_path, self.path)
                return affected
            finally:
                temporary_path.unlink(missing_ok=True)

    def _open_write(self, path: Path) -> TextIO:
        if self.path.suffix == ".gz":
            return gzip.open(path, mode="wt", encoding="utf-8", newline="")
        return path.open(mode="w", encoding="utf-8", newline="")
