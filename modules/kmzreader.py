# import kmz file

# Author:
# Linwood Creekmore III
# email: valinvescap@gmail.com

# Acknowledgements:
# http://programmingadvent.blogspot.com/2013/06/kmzkml-file-parsing-with-python.html
# http://gis.stackexchange.com/questions/159681/geopandas-cant-save-geojson

from io import BytesIO,StringIO
from zipfile import ZipFile
import re,os
import numpy as np
import xml.sax, xml.sax.handler
import pandas as pd

class PlacemarkHandler(xml.sax.handler.ContentHandler):
    def __init__(self):
        self.inName = False # handle XML parser events
        self.inPlacemark = False
        self.mapping = {} 
        self.buffer = ""
        self.name_tag = ""
        
    def startElement(self, name, attributes):
        if name == "Placemark": # on start Placemark tag
            self.inPlacemark = True
            self.buffer = "" 
        if self.inPlacemark:
            if name == "name": # on start title tag
                self.inName = True # save name text to follow
            
    def characters(self, data):
        if self.inPlacemark: # on text within tag
            self.buffer += data # save text if in title
            
    def endElement(self, name):
        self.buffer = self.buffer.strip('\n\t')
        
        if name == "Placemark":
            self.inPlacemark = False
            self.name_tag = "" #clear current name
        
        elif name == "name" and self.inPlacemark:
            self.inName = False # on end title tag            
            self.name_tag = self.buffer.strip()
            self.mapping[self.name_tag] = {}
        elif self.inPlacemark:
            if name in self.mapping[self.name_tag]:
                self.mapping[self.name_tag][name] += self.buffer
            else:
                self.mapping[self.name_tag][name] = self.buffer
        self.buffer = ""
        
    def spatializer(row):
        try:
            # look for the coordinates column
            data = row['coordinates'].strip(' \t\n\r')
        except:
            pass
        try:
            import shapely
            from shapely.geometry import Polygon,LineString,Point
        except ImportError as e:
            raise ImportError('This operation requires shapely. {0}'.format(e))
        import ast
        lsp = data.strip().split(' ')
        linestring = map(lambda x: ast.literal_eval(x),lsp)
        try:
            spatial = Polygon(LineString(linestring))
            convertedpoly = pd.Series({'geometry':spatial})
            return convertedpoly
        except:
            pass
            
        try:
            # Test for latitude and longitude columns
            lat=float(row['latitude'])
            lon=float(row['longitude'])
            point = Point(lon,lat)
            convertedpoly = pd.Series({'geometry':point})
            return convertedpoly
        except:
            
            pass
        
        
def keyholemarkup2x(file,output='df'):
    """
    Takes Keyhole Markup Language Zipped (KMZ) or KML file as input. The  
    output is a pandas dataframe, geopandas geodataframe, csv, geojson, or
    shapefile.
    
    All core functionality from:
    http://programmingadvent.blogspot.com/2013/06/kmzkml-file-parsing-with-python.html
    
    Parameters
        ----------
        file : {string}
            The string path to your KMZ or .
        output : {string}
            Defines the type of output. Valid selections include:
                - shapefile - 'shp', 'shapefile', or 'ESRI Shapefile'

        Returns
        -------
        self : object
    """
    r = re.compile(r'(?<=\.)km+[lz]?',re.I)
    try:
        extension = r.search(file).group(0) #(re.findall(r'(?<=\.)[\w]+',file))[-1]
        
    
    except IOError as e:
        logging.error("I/O error {0}".format(e))
    if (extension.lower()=='kml') is True:
        buffer = file
    elif (extension.lower()=='kmz') is True:
        kmz = ZipFile(file, 'r')
        
        vmatch = np.vectorize(lambda x:bool(r.search(x)))
        A = np.array(kmz.namelist())
        sel = vmatch(A)
        buffer = kmz.open(A[sel][0],'r')
    
    else:
        raise ValueError('Incorrect file format entered.  Please provide the '
                         'path to a valid KML or KMZ file.')    
     
    
    parser = xml.sax.make_parser()
    handler = PlacemarkHandler()
    parser.setContentHandler(handler)
    parser.parse(buffer)
    
    try:
        kmz.close()
    except:
        pass
    
    df = pd.DataFrame(handler.mapping).T
    names = list(map(lambda x: x.lower(),df.columns))
    
    
    output = output.lower()
    
    if output=='df' or output=='dataframe' or output == None:
        result = df
        
    elif output=='csv':
        out_filename = file[:-3] + "csv"
        df.to_csv(out_filename,encoding='utf-8',sep="\t")
        result = ("Successfully converted {0} to CSV and output to"
                   " disk at {1}".format(file,out_filename))
        
    elif output=='gpd' or output == 'gdf' or output=='geoframe' or output == 'geodataframe':
        try:
            import shapely
            from shapely.geometry import Polygon,LineString,Point
        except ImportError as e:
            raise ImportError('This operation requires shapely. {0}'.format(e))
        try:
            import fiona
        except ImportError as e:
            raise ImportError('This operation requires fiona. {0}'.format(e))
        try:
            import geopandas as gpd
        except ImportError as e:
            raise ImportError('This operation requires geopandas. {0}'.format(e))
            
        geos = gpd.GeoDataFrame(df.apply(PlacemarkHandler.spatializer,axis=1))
        result = gpd.GeoDataFrame(pd.concat([df,geos],axis=1))
        
        
    elif output=='geojson' or output=='json':
        try:
            import shapely
            from shapely.geometry import Polygon,LineString,Point
        except ImportError as e:
            raise ImportError('This operation requires shapely. {0}'.format(e))
        try:
            import fiona
        except ImportError as e:
            raise ImportError('This operation requires fiona. {0}'.format(e))
        try:
            import geopandas as gpd
        except ImportError as e:
            raise ImportError('This operation requires geopandas. {0}'.format(e))
        try:
            import geojson
        except ImportError as e:
            raise ImportError('This operation requires geojson. {0}'.format(e))
            
        geos = gpd.GeoDataFrame(df.apply(PlacemarkHandler.spatializer,axis=1))
        gdf = gpd.GeoDataFrame(pd.concat([df,geos],axis=1))
        out_filename = file[:-3] + "geojson"
        gdf.to_file(out_filename,driver='GeoJSON')
        validation = geojson.is_valid(geojson.load(open(out_filename)))['valid']
        if validation == 'yes':
            
            result = ("Successfully converted {0} to GeoJSON and output to"
                      " disk at {1}".format(file,out_filename))
        else:
            raise ValueError('The geojson conversion did not create a '
                            'valid geojson object. Try to clean your '
                            'data or try another file.')
            
    elif output=='shapefile' or output=='shp' or output =='esri shapefile':
        try:
            import shapely
            from shapely.geometry import Polygon,LineString,Point
        except ImportError as e:
            raise ImportError('This operation requires shapely. {0}'.format(e))
        try:
            import fiona
        except ImportError as e:
            raise ImportError('This operation requires fiona. {0}'.format(e))
            
        try:
            import geopandas as gpd
        except ImportError as e:
            raise ImportError('This operation requires geopandas. {0}'.format(e))
            
        try:
            import shapefile
        except ImportError as e:
            raise ImportError('This operation requires pyshp. {0}'.format(e))
        
            
        geos = gpd.GeoDataFrame(df.apply(PlacemarkHandler.spatializer,axis=1))
        gdf = gpd.GeoDataFrame(pd.concat([df,geos],axis=1))
        out_filename = file[:-3] + "shp"
        gdf.to_file(out_filename,driver='ESRI Shapefile')
        sf = shapefile.Reader(out_filename)
        import shapefile
        sf = shapefile.Reader(out_filename)
        if len(sf.shapes())>0:
            validation = "yes"
        else:
            validation = "no"
        if validation == 'yes':
            
            result = ("Successfully converted {0} to Shapefile and output to"
                      " disk at {1}".format(file,out_filename))
        else:
            raise ValueError('The Shapefile conversion did not create a '
                            'valid shapefile object. Try to clean your '
                            'data or try another file.') 
    else:
        raise ValueError('The conversion returned no data; check if'
                        ' you entered a correct output file type. '
                        'Valid output types are geojson, shapefile,'
                        ' csv, geodataframe, and/or pandas dataframe.')
        
    return result