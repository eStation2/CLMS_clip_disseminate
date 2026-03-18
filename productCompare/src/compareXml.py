import xml.etree.ElementTree as ET

from common import compare_file_info


def compare_xml(file1, file2):
    report = {
        'file_info': compare_file_info(file1, file2)
    }

    tree1 = ET.parse(file1)
    tree2 = ET.parse(file2)

    root1 = tree1.getroot()
    root2 = tree2.getroot()

    diffs = []
    
    def recursive_compare(elem1, elem2, path=""):
        if elem1.tag != elem2.tag:
            diffs.append(f"Different tags at {path}: {elem1.tag} vs {elem2.tag}")
        # Compare text content, handling None values
        text1 = elem1.text.strip() if elem1.text else ""
        text2 = elem2.text.strip() if elem2.text else ""
        if text1 != text2:
            diffs.append(f"Text mismatch at {path}/{elem1.tag}: '{text1}' vs '{text2}'")
        if elem1.attrib != elem2.attrib:
            diffs.append(f"Attributes mismatch at {path}/{elem1.tag}: {elem1.attrib} vs {elem2.attrib}")

        # Compare child elements, handling different numbers of children
        children1 = list(elem1)
        children2 = list(elem2)
        if len(children1) != len(children2):
            diffs.append(f"Different number of children at {path}/{elem1.tag}: {len(children1)} vs {len(children2)}")
            # Compare only the common children
            for i, (sub_elem1, sub_elem2) in enumerate(zip(children1, children2)):
                recursive_compare(sub_elem1, sub_elem2, f"{path}/{elem1.tag}[{i}]")
        else:
            for i, (sub_elem1, sub_elem2) in enumerate(zip(children1, children2)):
                recursive_compare(sub_elem1, sub_elem2, f"{path}/{elem1.tag}[{i}]")

    recursive_compare(root1, root2)
    
    report['diffs'] = diffs
    return report

if __name__ == "__main__":
    import argparse
    import json
    from pprint import pprint
    
    parser = argparse.ArgumentParser(description="Compare two xml files")
    parser.add_argument("ref_xml", type=str, help="Reference xml file")
    parser.add_argument("new_xml", type=str, help="New xml file")
    parser.add_argument("-r", "--reportFile", type=str, required=False, default=None, help="Report file - json file containing differences")
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress terminal output')
    
    args = parser.parse_args()  
    report = compare_xml(args.ref_xml, args.new_xml)

    if not args.quiet:
        pprint(report, sort_dicts=False)

    if args.reportFile:
        print(f"Saving report to {args.reportFile}")
        with open(args.reportFile, 'w') as fp:
            fp.write(json.dumps(report, indent=2))
