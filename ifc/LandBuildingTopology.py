import argparse
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import GEO, Namespace
from rdflib.plugins.sparql import prepareQuery
from osgeo import ogr

parser = argparse.ArgumentParser(description='Tool to produce discover topology '
                                             'relationships between 2D land parcel '
                                             'and 3D building data and matelise'
                                             'them in RDF triples.')
parser.add_argument('-lf', help='Land parcel file path in RDF with GML geometries. ', required=True)
parser.add_argument('-bf', help='Building file path in RDF with GML geometries. ', required=True)
parser.add_argument('--format', help='RDF file format', default="turtle")

args = parser.parse_args()
GML = Namespace("http://www.opengis.net/ont/gml#")

def map_land_geometries(g, file):
  ginvalid = Graph()
  map_geo = {}

  for s, p, o in g:
    if p == GEO.asGML:
      if 'srsDimension' not in o:
        o = o.replace('<gml:Polygon', '<gml:Polygon srsDimension="3" ')
      geom_shape = ogr.CreateGeometryFromGML(o)

      if not geom_shape.IsValid():
        valid_shape = geom_shape.MakeValid()
        if valid_shape is None:
          ginvalid.add((s, GEO.asWKT, Literal(geom_shape.ExportToWkt(), datatype=GEO.wktLiteral)))
        else:
          geom_shape = valid_shape
      if s not in map_geo.keys():
        map_geo[s] = geom_shape

  if ginvalid.all_nodes().__len__() != 0:
    new_invalid_file = file.split('.')[0] + 'invalid_wkt.ttl'
    ginvalid.serialize(destination=new_invalid_file, format=args.format)

  return map_geo

def map_footprint_geometries(g, file):
  ginvalid = Graph()
  map_geo = {}

  for s, p, o in g:
    if p == GEO.asGML:
      if 'srsDimension' not in o:
        o = o.replace('<gml:Polygon', '<gml:Polygon srsDimension="2" ')
      geom_shape = ogr.CreateGeometryFromGML(o)

      if not geom_shape.IsValid():
        valid_shape = geom_shape.MakeValid()
        if valid_shape is None:
          ginvalid.add((s, GEO.asWKT, Literal(geom_shape.ExportToWkt(), datatype=GEO.wktLiteral)))
        else:
          geom_shape = valid_shape
      if s not in map_geo.keys():
        map_geo[s] = geom_shape

  if ginvalid.all_nodes().__len__() != 0:
    new_invalid_file = file.split('.')[0] + 'invalid_wkt.ttl'
    ginvalid.serialize(destination=new_invalid_file, format=args.format)

  return map_geo

def evaluate_topology(geoA, geoB, keyA, keyB, topo_g):
  if geoA.Crosses(geoB):
    topo_g.add((URIRef(keyA), GEO.sfCrosses, URIRef(keyB)))
  if geoA.Contains(geoB):
    topo_g.add((URIRef(keyA), GEO.sfContains, URIRef(keyB)))
  if geoA.Overlaps(geoB):
    topo_g.add((URIRef(keyA), GEO.sfOverlaps, URIRef(keyB)))
  if geoA.Within(geoB):
    topo_g.add((URIRef(keyA), GEO.sfWithin, URIRef(keyB)))
  if geoA.Intersects(geoB):
    topo_g.add((URIRef(keyA), GEO.sfIntersects, URIRef(keyB)))
  return topo_g

land_g = Graph()
land_g.parse(args.lf)
bld_g = Graph()
bld_g.parse(args.bf)
topo_g = Graph()

land_geo = map_land_geometries(land_g, args.lf)
bld_geo = map_footprint_geometries(bld_g, args.bf)

for bld_key, bld_val in bld_geo.items():
  for land_key, land_val in land_geo.items():
    land_val_2d = land_val.FlattenTo2D() if land_val.GetCoordinateDimension() > 2 else land_val
    topo_g = evaluate_topology(bld_val, land_val_2d, bld_key, land_key, topo_g)
    topo_g = evaluate_topology(land_val_2d, bld_val, land_key, bld_key, topo_g)
  if bld_val.GetGeometryCount() > 0:
    for i in range(0, bld_val.GetGeometryCount()):
      g = bld_val.GetGeometryRef(i)
      for land_key, land_val_2d in land_geo.items():
        topo_g = evaluate_topology(g, land_val_2d, bld_key, land_key, topo_g)
        topo_g = evaluate_topology(land_val_2d, g, land_key, bld_key, topo_g)

topo_file = args.bf.split('.')[0] + '_topo_' +  args.lf.split('/')[-1]
topo_g.serialize(topo_file, format=args.format)
print(topo_file)