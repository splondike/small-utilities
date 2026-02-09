#!/usr/bin/env python3 -u
"""
HTTP GET client that can cache to local disk and revalidate existing downloads
using Etag. Can also download multiple files in one invocation to amortise
the cost of booting the CLI.
"""

import argparse
import concurrent.futures
import csv
import datetime
import json
import hashlib
import pathlib
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


class CachingHttpClient():
    """
    Performs GET requests and caches them on the local filesystem. Uses the
    etag header to avoid unnecessary downloads.
    """

    CONTENT_TYPE_MAPPING = {
        "application/json": "json",
        "application/pdf": "pdf",
        "application/xml": "xml",
        "text/csv": "csv",
        "text/html": "html",
        "text/markdown": "md",
        "text/plain": "text",
    }

    def __init__(self, app_name: str = None, cache_dir: str = None):
        self.app_name = app_name
        self.cache_dir = cache_dir
        self.requestor = self._default_requestor
        if self.cache_dir is None:
            self.cache_dir = (
                pathlib.Path.home() / ".cache" / "httpcache" / self.app_name
            )

    def url_get(self, url: str, min_cache_time_s=0) -> pathlib.Path:
        base_filename = hashlib.sha256(url.encode()).hexdigest()
        metadata_filename = self.cache_dir / (base_filename + ".json")

        headers = {
            # Many servers give bogus responses to the default python UA
            "User-Agent": self.app_name
        }

        if metadata_filename.exists():
            with open(metadata_filename, "rb") as fh:
                metadata = json.load(fh)
                if "etag" in metadata and metadata["etag"] is not None:
                    headers["If-None-Match"] = metadata["etag"]
            validated = datetime.datetime.fromisoformat(
                metadata["last_validated_at"]
            )
            if (
                datetime.datetime.now() - validated
            ).seconds < min_cache_time_s:
                content_filename = self._calculate_content_filename(
                    base_filename,
                    metadata["extension"]
                )
                with open(content_filename, "rb") as fh:
                    return content_filename

        request_time = datetime.datetime.now().isoformat()
        response = self.requestor("GET", url, headers)
        if response["status_code"] == 200:
            # Cache it
            extension = self.CONTENT_TYPE_MAPPING.get(
                response["headers"]["content-type"].split(";")[0],
                "bin"
            )
            content_filename = self._calculate_content_filename(
                base_filename,
                extension
            )
            content_filename.parent.mkdir(parents=True, exist_ok=True)
            with open(content_filename, "wb") as fh:
                fh.write(response["body"])

            metadata = {
                "url": url,
                "last_validated_at": request_time,
                "extension": extension,
                "etag": response["headers"].get("etag")
            }
            with open(metadata_filename, "w") as fh:
                json.dump(metadata, fh)

            return content_filename
        elif response["status_code"] == 304:
            with open(metadata_filename, "rb") as fh:
                metadata = json.load(fh)
            metadata["last_validated_at"] = request_time
            with open(metadata_filename, "w") as fh:
                json.dump(metadata, fh)
            return self._calculate_content_filename(
                base_filename,
                metadata["extension"]
            )
        else:
            # It is a little weird catching and then re-raising this error,
            # but it makes mocking the requestor interface a bit more
            # uniform I think.
            raise urllib.error.HTTPError(
                url,
                response["status_code"],
                f"Error status code: {response['status_code']}",
                {},
                None
            )

    def _calculate_content_filename(self, base_filename: str, extension: str):
        """
        Include a standard file extension so tools like w3m can guess how to
        parse it better
        """

        return self.cache_dir / (base_filename + ".data." + extension)

    @staticmethod
    def _default_requestor(
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Any] = None,
        raw_data: Optional[bytes] = None,
        timeout: int = 30
    ) -> dict:
        if raw_data is not None:
            request_data = raw_data
        elif json_data is not None:
            request_data = json.dumps(json_data).encode()
        else:
            request_data = None

        try:
            response = urllib.request.urlopen(
                urllib.request.Request(
                    url,
                    method=method,
                    data=request_data,
                    headers=headers if headers is not None else {},
                ),
                timeout=timeout
            )
        except urllib.error.HTTPError as e:
            response = e

        return {
            "status_code": response.status,
            "headers": dict({
                k.lower(): v
                for k, v in response.getheaders()
            }),
            "body": response.read()
        }


def main():
    parser = argparse.ArgumentParser(
        description="Script for HTTP GET that caches files to local disk"
    )

    parser.add_argument("app_name", help="The name of your disk cache")
    parser.add_argument(
        "url",
        nargs="+",
        help="The URL to fetch, or - to read from stdin"
    )
    parser.add_argument(
        "--output-format",
        choices=["path", "csv"],
        default="path",
        help="The name of your disk cache"
    )
    parser.add_argument(
        "--max-threads",
        type=int,
        default=4,
        help=(
            "How many urls to download in parallel"
        )
    )
    parser.add_argument(
        "--min-cache-time",
        type=int,
        default=0,
        help=(
            "Force cache reuse if last request to URL was within this "
            "many seconds"
        )
    )

    args = parser.parse_args()

    client = CachingHttpClient(app_name=args.app_name)

    csv_writer = csv.DictWriter(sys.stdout, fieldnames=["url", "status", "file"])
    iterator = sys.stdin.readlines if args.url[0] == "-" else lambda: args.url
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.max_threads
    ) as pool:
        for idx, url, future in zip(
            range(len(args.url)),
            args.url,
            [pool.submit(client.url_get, url) for url in iterator()]
        ):
            if args.output_format == "csv":
                if idx == 0:
                    csv_writer.writeheader()
                try:
                    csv_writer.writerow({
                        "url": url,
                        "status": "ok",
                        "file": future.result(),
                    })
                except urllib.error.HTTPError as e:
                    csv_writer.writerow({
                        "url": url,
                        "status": str(e.code),
                        "file": "",
                    })
            else:
                sys.stdout.write(f"{future.result()}\n")


if __name__ == "__main__":
    main()
