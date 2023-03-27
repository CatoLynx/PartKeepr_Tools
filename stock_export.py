import argparse
import json

from partkeepr import PartKeepr
from secrets import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mapping", type=str, required=True, help="Stock export mapping from PartKeepr part number to export key name (JSON)")
    parser.add_argument("-o", "--output", type=str, required=True, help="Output file name (JSON)")
    args = parser.parse_args()
    
    pk = PartKeepr(PK_BASE_URL, PK_USERNAME, PK_PASSWORD)
    with open(args.mapping, 'r') as f:
        mapping = json.load(f)
    
    output = {}
    for pk_id, name in mapping.items():
        part = pk.get_part(pk_id)
        output[name] = part['stockLevel']
    
    with open(args.output, 'w') as f:
        json.dump(output, f)


if __name__ == "__main__":
    main()
