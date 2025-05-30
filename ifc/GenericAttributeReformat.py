import argparse
import xml.etree.ElementTree as ET
import uuid

parser = argparse.ArgumentParser(description='Simple app reformatting GML '
                                             'GenericAttibutes: by adding UUIDs '
                                             'and making "name" XML attribute'
                                             'XML child element of GenericAttibute.')
parser.add_argument('-f', help='GML file path', required=True)

def transform_xml(source_xml):
  # Parse the source XML
  tree = ET.parse(source_xml)

  def transform_element(elem):
    # Find the "*Attribute" element
    if 'Attribute' in elem.tag:
      # Generate a UUID for the "*Attribute" element
      elem.set("ns1:id", str(uuid.uuid4()))

      # make 'name' XML attribute GML element
      if len(elem.attrib) != 0:
        rem = 0
        for key, value in elem.attrib.items():
          if key == 'name':
            rem = 1
            nameel = ET.Element('ns3:name')
            nameel.text = value
            elem.append(nameel)
        if rem == 1:
          del elem.attrib['name']

  def transform_root(tree):
    # Recursively traverse the XML tree and transform elements
    for elem in tree.iter():
      transform_element(elem)

  transform_root(tree)

  return tree

args = parser.parse_args()

with open(args.f.split('.')[0] + '_reformatted.gml', 'wb') as f:
  transform_xml(args.f).write(f)