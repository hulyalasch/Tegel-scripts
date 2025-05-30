import argparse
from io import BytesIO
from pyproj import CRS
from pyogrio import write_dataframe
from rdflib import Graph, Literal
from rdflib.namespace import GEO, Namespace
from rdflib.plugins.sparql import prepareQuery
from osgeo import ogr
import geopandas as gpd
from shapely import from_wkt

parser = argparse.ArgumentParser(description='Simple app replacing GML '
                                             'geometry representations with '
                                             'WKT and KML or GeoJSON in RDF graphs. '
                                             'It requires GDAL in the system to work.')
parser.add_argument('-f', help='RDF file path', required=True)
parser.add_argument('--format', help='RDF file format', default="turtle")

GML = Namespace("http://www.opengis.net/ont/gml#")

args = parser.parse_args()

g = Graph()
g.parse(args.f)

ginvalid = Graph()

crs_id = 'http://www.opengis.net/def/crs/EPSG/0/25833'


def transform_geometry_to_literal(wkt, driver):
  try:
    wkt_object = from_wkt(wkt)
    gdf = gpd.GeoDataFrame(geometry=[wkt_object],
                           crs=CRS.from_user_input(crs_id))
    literal_string = transform_geodataframe_to_literal(gdf, driver)
  except Exception as e:
    print(repr(e))
    literal_string = ''

  return literal_string


def transform_geodataframe_to_literal(gdf, driver):
  try:
    buffer = BytesIO()
    write_dataframe(gdf.to_crs(4326), buffer, driver=driver)
    literal_string = buffer.read().decode()
  except Exception as e:
    print(repr(e))
    literal_string = ''

  return literal_string


surfaceMembers = prepareQuery(
    "SELECT ?sm WHERE { ?geometry gml:surfaceMember ?sm .}",
    initNs={"gml": GML}
)

surfaceMemberGML = prepareQuery(
    "SELECT ?gml WHERE { ?geometry geo:asGML ?gml .}",
    initNs={"geo": GEO}
)


def transformSurfaceGeometries(graph, ginvalid, driver):
  try:
    driverToDatatype = {'GeoJSON': GEO.geoJSONLiteral, 'KML': GEO.kmlLiteral}
    driverToPredicate = {'GeoJSON': GEO.asGeoJSON, 'KML': GEO.asKML}
    geometries = []
    for s, p, o in graph:
      if p == GEO.hasDefaultGeometry:
        surfaces = graph.query(surfaceMembers, initBindings={'geometry': o})
        if len(surfaces) > 0 and s not in geometries:
          geometries.append(o)
          wkts = []
          for row in surfaces:
            wkt = get_wkt_for_geometry(row.sm, graph, ginvalid)
            if wkt != '':
              wkts.append(from_wkt(wkt))
          gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(wkts),
                                 crs=CRS.from_user_input(crs_id))
          gdf.crs = CRS.from_user_input(crs_id)
          literal = transform_geodataframe_to_literal(gdf, driver)
          if literal != '':
            graph.add((o, driverToPredicate.get(driver),
                       Literal(literal, datatype=driverToDatatype.get(driver))))
        else:
          wkt = get_wkt_for_geometry(o, graph, ginvalid)
          if wkt != '':
            literal = transform_geometry_to_literal(wkt, driver)
            if literal != '':
              graph.add((o, driverToPredicate.get(driver),
                         Literal(literal, datatype=driverToDatatype.get(driver))))
  except Exception as e:
    print(repr(e))


def get_wkt_for_geometry(geometry, graph, ginvalid):
  gml_query = graph.query(surfaceMemberGML, initBindings={'geometry': geometry})
  gml_str = next(iter(gml_query)).gml
  wkt = validateAndTransformGmlToWkt(gml_str, geometry, graph, ginvalid)

  return wkt


def geoDataFrameToLiteral(gdf, driver):
  buffer = BytesIO()
  write_dataframe(gdf.to_crs(4326), buffer, driver=driver)
  literal_string = buffer.read().decode()

  return literal_string


def validateAndTransformGmlToWkt(gml, geom, graph, ginvalid):
  try:
    invalid = 0
    gml_orig = gml
    if 'srsDimension' not in gml:
      gml = gml.replace('<gml:Polygon', '<gml:Polygon srsDimension="3" ')
    geom_shape = ogr.CreateGeometryFromGML(gml)
    wkt = geom_shape.ExportToWkt()
    if not wkt is None:
      if not geom_shape.IsValid():
        valid_shape = geom_shape.MakeValid()
        if valid_shape is None:
          invalid = 1
          ginvalid.add((geom, GEO.asWKT, Literal(wkt, datatype=GEO.wktLiteral)))
        else:
          wkt = valid_shape.ExportToWkt()
          if not wkt is None:
            wkt_crs = '<' + crs_id + '> ' + wkt
            graph.add(
                (geom, GEO.asWKT, Literal(wkt_crs, datatype=GEO.wktLiteral)))
            graph.remove((geom, GEO.asGML, gml_orig))
      else:
        wkt_crs = '<' + crs_id + '> ' + wkt
        graph.add((geom, GEO.asWKT, Literal(wkt_crs, datatype=GEO.wktLiteral)))
        graph.remove((geom, GEO.asGML, gml_orig))
    if invalid == 1:
      wkt = ''
  except Exception as e:
    print(repr(e))

  return wkt


transformSurfaceGeometries(g, ginvalid, 'GeoJSON')

new_file = args.f.split('.')[0] + '_wkt.ttl'
new_invalid_file = args.f.split('.')[0] + 'invalid_wkt.ttl'

g.serialize(destination=new_file, format=args.format)
ginvalid.serialize(destination=new_invalid_file, format=args.format)
