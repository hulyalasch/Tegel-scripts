import argparse
from rdflib import Graph, Literal
from rdflib.namespace import GEO, XSD
from osgeo import ogr

parser = argparse.ArgumentParser(description='Tool to calculate areas of'
                                             'geometries in RDF stored in'
                                             'WKT format. Assumes geometries are'
                                             'in metric SRS.')
parser.add_argument('-f', help='RDF file path with WKT geometries. ', required=True)
parser.add_argument('--format', help='RDF file format', default="turtle")

args = parser.parse_args()

g = Graph()
g.parse(args.f)

for s, p, o in g:
  if p == GEO.asWKT:
    geom_shape = ogr.CreateGeometryFromWkt(o.replace("<http://www.opengis.net/def/crs/EPSG/0/25833>", ""))
    if not geom_shape is None:
      area = geom_shape.GetArea()
      g.add((s, GEO.hasMetricArea, Literal(area, datatype=XSD.double)))

new_file= args.f.split('.')[0] + '_with_areas.' +  args.f.split('.')[-1]
g.serialize(destination=new_file, format=args.format)
