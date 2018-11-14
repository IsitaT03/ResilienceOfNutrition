import numpy as np
import hazelbean as hb
import pandas as pd


import gdal
import pygeoprocessing

def area_of_pixel(pixel_size, center_lat):
    """Calculate m^2 area of a wgs84 square pixel.

    Adapted from: https://gis.stackexchange.com/a/127327/2397

    Parameters:
        pixel_size (float): length of side of pixel in degrees.
        center_lat (float): latitude of the center of the pixel. Note this
            value +/- half the `pixel-size` must not exceed 90/-90 degrees
            latitude or an invalid area will be calculated.

    Returns:
        Area of square pixel of side length `pixel_size` centered at
        `center_lat` in m^2.

    """
    a = 6378137  # meters
    b = 6356752.3142  # meters
    e = np.sqrt(1-(b/a)**2)
    area_list = []
    for f in [center_lat+pixel_size/2, center_lat-pixel_size/2]:
        zm = 1 - e*np.sin(np.radians(f))
        zp = 1 + e*np.sin(np.radians(f))
        area_list.append(
            np.pi * b**2 * (
                np.log(zp/zm) / (2*e) +
                np.sin(np.radians(f)) / (zp*zm)))
    return pixel_size / 360. * (area_list[0]-area_list[1])

def resample_raster(inputfile_path, referencefile_path, outputfile_path,band_num=1):
             
    input_raster = gdal.Open(inputfile_path, gdalconst.GA_ReadOnly)
    input_band = input_raster.GetRasterBand(band_num)
    inputProj = input_raster.GetProjection()
    inputTrans = input_raster.GetGeoTransform()

    reference = gdal.Open(referencefile_path, gdalconst.GA_ReadOnly)
    referenceProj = reference.GetProjection()
    referenceTrans = reference.GetGeoTransform()
    bandreference = reference.GetRasterBand(1)    
    x = reference.RasterXSize 
    y = reference.RasterYSize

    driver= gdal.GetDriverByName('GTiff')
    output = driver.Create(outputfile_path,x,y,1,bandreference.DataType)
    output.SetGeoTransform(referenceTrans)
    output.SetProjection(referenceProj)

    gdal.ReprojectImage(input_raster,output,inputProj,referenceProj,gdalconst.GRA_Bilinear)

    del output


def convert_af_to_1d_df(af):
    array = af.data.flatten()
    df = pd.DataFrame(array)
    return df


def concatenate_dfs_horizontally(df_list, column_headers=None):
    """
    Append horizontally, based on index.
    """
    df = pd.concat(df_list, axis=1)
    if column_headers:
        df.columns = column_headers
    return df

def create_land_mask():
    countries_af = hb.ArrayFrame('../Data/inputs/Base/country_ids.tif')
    df = convert_af_to_1d_df(countries_af)
    df['land_mask'] = df[0].apply(lambda x: 1 if x > 0 else 0)
    df = df.drop(0, axis=1)
    return df

def rasters_to_tabular_csv(rasters_paths,csv_name,
                          latlon=False,col_names=None):
    # Create tabular data
    rasters_names = []
    dfs_list = []

    match_af = hb.ArrayFrame(rasters_paths[0])
    for path in rasters_paths:
        af = hb.ArrayFrame(path)
        df = convert_af_to_1d_df(af)
        dfs_list.append(df)
    
        name = hb.explode_path(path)['file_root_no_suffix']
        rasters_names.append(name)
        
    if col_names == None:
        col_names = rasters_names
        
    df = concatenate_dfs_horizontally(dfs_list, col_names)

    # Remove NaNs
    # Or don't ?

    # Get rid of the oceans cells
    df['pixel_id'] = df.index
    #df['pixel_id_float'] = df['pixel_id'].astype('float')
    land_mask = create_land_mask()
    df = df.merge(land_mask, right_index=True, left_on='pixel_id')
    df_land = df[df['land_mask']==1]
    df_land = df_land.dropna()

    if latlon == True:
        df_land['lon'] = round( (((df['pixel_id'] % 4320.)/4320 - .5) * 360.0),2)
        df_land['lat'] = round( (((df['pixel_id'] / 4320.).round()/2160 - .5) * 180.),2)
    
    
    dfland = df_land.set_index('pixel_id')

    print('Writing csv ' + csv_name)
    df_land.to_csv('../Data/intermediate/'+csv_name+'.csv')

