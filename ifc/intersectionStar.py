import argparse
from rdflib import Graph, Namespace
from shapely import wkt
from osgeo import ogr
import re

GEO = Namespace("http://www.opengis.net/ont/geosparql#")

def gml_to_shapely(gml):
    geom_shape = ogr.CreateGeometryFromGML(gml)
    if geom_shape is not None:
        if geom_shape.GetCoordinateDimension() > 2:
            geom_shape = geom_shape.FlattenTo2D()
        geom_shape = geom_shape.GetLinearGeometry()
        return wkt.loads(geom_shape.ExportToWkt())
    else:
        return None

def wkt_to_shapely(wkt_literal):
    return wkt.loads(wkt_literal)

def get_polygons(graph):
    polygons = {}
    for s, p, o in graph:
        if p == GEO.asGML:
            poly = gml_to_shapely(str(o))
            if poly:
                polygons[s] = poly
        elif p == GEO.asWKT:
            m = re.match(r'<[^>]*>\s*(.+)', str(o))
            wkt_geom = m.group(1) if m else str(o)
            try:
                poly = wkt_to_shapely(wkt_geom)
                polygons[s] = poly
            except Exception:
                pass
    return polygons

def main():
    parser = argparse.ArgumentParser(description="Calculate intersection areas between land and building polygons from RDF/TTL, output as RDF-star.")
    parser.add_argument('-lf', '--land', required=True, help='Land plan TTL file')
    parser.add_argument('-bf', '--footprint', required=True, help='Building footprint TTL file')
    parser.add_argument('-o', '--output', required=True, help='Output TTL file')
    args = parser.parse_args()

    land_graph = Graph()
    land_graph.parse(args.land, format="ttl")
    building_graph = Graph()
    building_graph.parse(args.footprint, format="ttl")

    land_polygons = get_polygons(land_graph)
    building_polygons = get_polygons(building_graph)

    with open(args.output, "w") as f:
        f.write("@prefix geo: <http://www.opengis.net/ont/geosparql#> .\n\n")
        for land_uri, land_poly in land_polygons.items():
            for bld_uri, bld_poly in building_polygons.items():
                inter = land_poly.intersection(bld_poly)
                if not inter.is_empty and inter.area > 0:
                    subj = land_uri.n3()
                    obj = bld_uri.n3()
                    f.write(f"<< {subj} geo:sfIntersects {obj} >> geo:hasMetricArea {inter.area} .\n")

if __name__ == "__main__":
    main()
