import fiona
import geopandas as gpd
from pyproj import CRS
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.ops import unary_union
from lxml import etree

# Step 1: Read triangles from GML file
import argparse

parser = argparse.ArgumentParser(description="Convert GML triangle geometries to CityGML MultiSurface")
parser.add_argument("--input", "-i", required=True, help="Path to input GML file")
parser.add_argument("--output", "-o", default="footprint.gml", help="Path to output GML file")
args = parser.parse_args()
 
gml_file_path = args.input
output_file_path = args.output
with fiona.open(gml_file_path, driver="GML") as src:
    geometries = [shape(feature["geometry"]) for feature in src]

# Step 2: Assign CRS and perform unary union

# Assign CRS EPSG:25833 to triangle geometries
gdf = gpd.GeoDataFrame(geometry=geometries, crs=CRS.from_epsg(25833))
triangles = list(gdf.geometry)
merged_geometry = unary_union(triangles)

# Step 3: Extract bounding box coordinates
envelope = merged_geometry.envelope
envelope_coords = list(envelope.exterior.coords)

# Step 4: Create CityGML 2.0-compliant document
CITYGML_NS = "http://www.opengis.net/citygml/2.0"
GML_NS = "http://www.opengis.net/gml"
NSMAP_CITYGML = {
    # Removed default namespace to avoid XSPARQL QName conflict
    "gml": GML_NS,
    "core": CITYGML_NS,
    "bldg": "http://www.opengis.net/citygml/building/2.0"
}

city_model = etree.Element(etree.QName(NSMAP_CITYGML["core"], "CityModel"), nsmap=NSMAP_CITYGML)

# Add <gml:boundedBy> with Envelope
bounded_by = etree.SubElement(city_model, etree.QName(GML_NS, "boundedBy"))
env = etree.SubElement(bounded_by, etree.QName(GML_NS, "Envelope"), srsName="EPSG:25833")
lower = etree.SubElement(env, etree.QName(GML_NS, "lowerCorner"))
upper = etree.SubElement(env, etree.QName(GML_NS, "upperCorner"))
lower.text = f"{envelope_coords[0][0]} {envelope_coords[0][1]}"
upper.text = f"{envelope_coords[2][0]} {envelope_coords[2][1]}"

# Add <gml:featureMember> and <core:Building>
feature_member = etree.SubElement(city_model, etree.QName(GML_NS, "featureMember"))
building = etree.SubElement(feature_member, etree.QName(NSMAP_CITYGML['bldg'], "Building"), attrib={etree.QName(GML_NS, "id"): "bldg1"})

lod0_footprint = etree.SubElement(building, etree.QName(NSMAP_CITYGML['bldg'], "lod0FootPrint"))
multi_surface = etree.SubElement(lod0_footprint, etree.QName(GML_NS, "MultiSurface"), attrib={"srsName": "urn:ogc:def:crs:EPSG:25833"})

# Step 5: Convert merged geometry into smallest set of polygons
if merged_geometry.geom_type == "Polygon":
    polygons = [merged_geometry]
elif merged_geometry.geom_type == "MultiPolygon":
    polygons = list(merged_geometry.geoms)

# Step 6: Add each polygon as <gml:surfaceMember>
for i, poly in enumerate(polygons):
    surface_member = etree.SubElement(multi_surface, etree.QName(GML_NS, "surfaceMember"))
    polygon_elem = etree.SubElement(surface_member, etree.QName(GML_NS, "Polygon"), attrib={etree.QName(GML_NS, "id"): f"poly_{i}", "srsName": "urn:ogc:def:crs:EPSG:25833"})
    exterior = etree.SubElement(polygon_elem, etree.QName(GML_NS, "exterior"))
    linear_ring_elem = etree.SubElement(exterior, etree.QName(GML_NS, "LinearRing"))
    pos_list = etree.SubElement(linear_ring_elem, etree.QName(GML_NS, "posList"))
    coords_text = " ".join(f"{coord[0]} {coord[1]}" for coord in poly.exterior.coords)
    pos_list.text = coords_text

# Step 7: Write output CityGML file
with open(output_file_path, "wb") as f:
    f.write(etree.tostring(city_model, pretty_print=True, xml_declaration=True, encoding="UTF-8"))
