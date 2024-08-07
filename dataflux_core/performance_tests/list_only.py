"""
 Copyright 2024 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 """

import argparse
import time

from dataflux_core import download, fast_list


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=str)
    parser.add_argument("--bucket", type=str)
    parser.add_argument("--bucket-file-count", type=int, default=None)
    parser.add_argument("--bucket-file-size", type=int, default=None)
    parser.add_argument("--num-workers", type=int, default=10)
    parser.add_argument("--max-compose-bytes", type=int, default=100000000)
    parser.add_argument("--prefix", type=str, default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    list_start_time = time.time()
    print(f"Listing operation started at {list_start_time}")
    list_result = fast_list.ListingController(args.num_workers,
                                              args.project,
                                              args.bucket,
                                              prefix=args.prefix).run()
    list_end_time = time.time()
    if args.bucket_file_count and len(list_result) != args.bucket_file_count:
        raise AssertionError(
            f"Expected {args.bucket_file_count} files, but got {len(list_result)}"
        )
    print(
        f"{len(list_result)} objects listed in {list_end_time - list_start_time} seconds"
    )


if __name__ == "__main__":
    main()
