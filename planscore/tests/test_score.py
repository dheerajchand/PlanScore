import unittest, unittest.mock, io, os, contextlib, json, gzip, itertools
from .. import score, data
import botocore.exceptions
from osgeo import ogr, gdal

should_gzip = itertools.cycle([True, False])

# Don't clutter output when running invalid data in tests
gdal.PushErrorHandler('CPLQuietErrorHandler')

def mock_s3_get_object(Bucket, Key):
    '''
    '''
    path = os.path.join(os.path.dirname(__file__), 'data', Key)
    if not os.path.exists(path):
        raise botocore.exceptions.ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
    with open(path, 'rb') as file:
        if next(should_gzip):
            return {'Body': io.BytesIO(gzip.compress(file.read())),
                'ContentEncoding': 'gzip'}
        else:
            return {'Body': io.BytesIO(file.read())}

class TestScore (unittest.TestCase):

    def test_calculate_gap_fair(self):
        ''' Efficiency gap can be correctly calculated for a fair election
        '''
        input = data.Upload(id=None, key=None,
            districts = [
                dict(totals={'Voters': 10, 'Red Votes': 2, 'Blue Votes': 6}, tile=None),
                dict(totals={'Voters': 10, 'Red Votes': 3, 'Blue Votes': 5}, tile=None),
                dict(totals={'Voters': 10, 'Red Votes': 5, 'Blue Votes': 3}, tile=None),
                dict(totals={'Voters': 10, 'Red Votes': 6, 'Blue Votes': 2}, tile=None),
                ])
        
        output = score.calculate_gap(input)
        self.assertEqual(output.summary['Efficiency Gap'], 0)

    def test_calculate_gap_unfair(self):
        ''' Efficiency gap can be correctly calculated for an unfair election
        '''
        input = data.Upload(id=None, key=None,
            districts = [
                dict(totals={'Voters': 10, 'Red Votes': 1, 'Blue Votes': 7}, tile=None),
                dict(totals={'Voters': 10, 'Red Votes': 5, 'Blue Votes': 3}, tile=None),
                dict(totals={'Voters': 10, 'Red Votes': 5, 'Blue Votes': 3}, tile=None),
                dict(totals={'Voters': 10, 'Red Votes': 5, 'Blue Votes': 3}, tile=None),
                ])
        
        output = score.calculate_gap(input)
        self.assertEqual(output.summary['Efficiency Gap'], -.25)

    def test_calculate_gap_ushouse(self):
        ''' Efficiency gap can be correctly calculated for a U.S. House election
        '''
        input = data.Upload(id=None, key=None,
            districts = [
                dict(totals={'US House Rep Votes': 2, 'US House Dem Votes': 6}, tile=None),
                dict(totals={'US House Rep Votes': 3, 'US House Dem Votes': 5}, tile=None),
                dict(totals={'US House Rep Votes': 5, 'US House Dem Votes': 3}, tile=None),
                dict(totals={'US House Rep Votes': 6, 'US House Dem Votes': 2}, tile=None),
                ])
        
        output = score.calculate_gap(input)
        self.assertEqual(output.summary['US House Efficiency Gap'], 0)

    def test_calculate_gap_ushouse(self):
        ''' Efficiency gap can be correctly calculated for a State upper house election
        '''
        input = data.Upload(id=None, key=None,
            districts = [
                dict(totals={'SLDU Rep Votes': 2, 'SLDU Dem Votes': 6}, tile=None),
                dict(totals={'SLDU Rep Votes': 3, 'SLDU Dem Votes': 5}, tile=None),
                dict(totals={'SLDU Rep Votes': 5, 'SLDU Dem Votes': 3}, tile=None),
                dict(totals={'SLDU Rep Votes': 6, 'SLDU Dem Votes': 2}, tile=None),
                ])
        
        output = score.calculate_gap(input)
        self.assertEqual(output.summary['SLDU Efficiency Gap'], 0)

    def test_calculate_gap_ushouse(self):
        ''' Efficiency gap can be correctly calculated for a State lower house election
        '''
        input = data.Upload(id=None, key=None,
            districts = [
                dict(totals={'SLDL Rep Votes': 2, 'SLDL Dem Votes': 6}, tile=None),
                dict(totals={'SLDL Rep Votes': 3, 'SLDL Dem Votes': 5}, tile=None),
                dict(totals={'SLDL Rep Votes': 5, 'SLDL Dem Votes': 3}, tile=None),
                dict(totals={'SLDL Rep Votes': 6, 'SLDL Dem Votes': 2}, tile=None),
                ])
        
        output = score.calculate_gap(input)
        self.assertEqual(output.summary['SLDL Efficiency Gap'], 0)

    def test_score_district(self):
        ''' District scores are correctly read from input GeoJSON
        '''
        s3, bucket = unittest.mock.Mock(), unittest.mock.Mock()
        s3.get_object.side_effect = mock_s3_get_object
        
        with open(os.path.join(os.path.dirname(__file__), 'data', 'null-plan.geojson')) as file:
            geojson = json.load(file)
        
        feature1, feature2 = geojson['features']

        geometry1 = ogr.CreateGeometryFromJson(json.dumps(feature1['geometry']))
        totals1, tiles1, _ = score.score_district(s3, bucket, geometry1, 'XX')

        geometry2 = ogr.CreateGeometryFromJson(json.dumps(feature2['geometry']))
        totals2, tiles2, _ = score.score_district(s3, bucket, geometry2, 'XX')
        
        self.assertAlmostEqual(totals1['Voters'] + totals2['Voters'], 15)
        self.assertAlmostEqual(totals1['Blue Votes'] + totals2['Blue Votes'], 6)
        self.assertAlmostEqual(totals1['Red Votes'] + totals2['Red Votes'], 6)
        self.assertEqual(tiles1, ['12/2047/2047', '12/2047/2048'])
        self.assertEqual(tiles2, ['12/2047/2047', '12/2048/2047', '12/2047/2048', '12/2048/2048'])
    
    def test_score_district_invalid_geom(self):
        ''' District scores are correctly read despite topology error.
        '''
        s3, bucket = unittest.mock.Mock(), unittest.mock.Mock()
        s3.get_object.side_effect = mock_s3_get_object
        
        with open(os.path.join(os.path.dirname(__file__), 'data', 'NC-plan-1-992.geojson')) as file:
            geojson = json.load(file)
        
        feature = geojson['features'][0]

        geometry = ogr.CreateGeometryFromJson(json.dumps(feature['geometry']))
        totals, tiles, _ = score.score_district(s3, bucket, geometry, 'NC')
        
        self.assertAlmostEqual(totals['Voters'], 621.0287544586728)
        self.assertAlmostEqual(totals['Blue Votes'], 866.9575196315632)
        self.assertAlmostEqual(totals['Red Votes'], 811.4376789272283)
        self.assertEqual(tiles, ['12/1104/1612'])
    
    def test_score_district_missing_tile(self):
        ''' District scores come up empty for an area with no tiles
        '''
        s3, bucket = unittest.mock.Mock(), unittest.mock.Mock()
        s3.get_object.side_effect = mock_s3_get_object
        
        with open(os.path.join(os.path.dirname(__file__), 'data', 'null-ranch.geojson')) as file:
            geojson = json.load(file)
        
        feature = geojson['features'][0]
        geometry = ogr.CreateGeometryFromJson(json.dumps(feature['geometry']))
        totals, tiles, _ = score.score_district(s3, bucket, geometry, 'XX')

        self.assertFalse(totals['Voters'])
        self.assertFalse(tiles)
    
    @unittest.mock.patch('planscore.score.score_district')
    def test_score_plan_geojson(self, score_district):
        ''' District plan scores can be read from a GeoJSON source
        '''
        score_district.return_value = {'Red Votes': 0, 'Blue Votes': 1}, \
            ['zxy'], 'Better score a district.\n'
        
        plan_path = os.path.join(os.path.dirname(__file__), 'data', 'null-plan.geojson')
        upload = data.Upload('id', os.path.basename(plan_path), [])
        
        scored, output = score.score_plan(None, None, upload, plan_path, None)
        self.assertIn('2 features in 1119-byte null-plan.geojson', output)
        self.assertIn('Better score a district.', output)
        self.assertEqual(scored.districts, [{'totals': {'Red Votes': 0, 'Blue Votes': 1}, 'tiles': ['zxy']}] * 2)
        self.assertEqual(scored.summary['Efficiency Gap'], -.5)
    
    @unittest.mock.patch('planscore.score.score_district')
    def test_score_plan_gpkg(self, score_district):
        ''' District plan scores can be read from a Geopackage source
        '''
        score_district.return_value = {'Red Votes': 1, 'Blue Votes': 0}, \
            ['zxy'], 'Better score a district.\n'
        
        plan_path = os.path.join(os.path.dirname(__file__), 'data', 'null-plan.gpkg')
        upload = data.Upload('id', os.path.basename(plan_path), [])
        
        scored, output = score.score_plan(None, None, upload, plan_path, None)
        self.assertIn('2 features in 40960-byte null-plan.gpkg', output)
        self.assertIn('Better score a district.', output)
        self.assertEqual(scored.districts, [{'totals': {'Red Votes': 1, 'Blue Votes': 0}, 'tiles': ['zxy']}] * 2)
        self.assertEqual(scored.summary['Efficiency Gap'], .5)
    
    @unittest.mock.patch('planscore.score.score_district')
    def test_score_plan_missing_tile(self, score_district):
        ''' District plan scores come up empty for an area with no tiles
        '''
        score_district.return_value = {'Red Votes': 0, 'Blue Votes': 0}, \
            ['zxy'], 'Better score a district.\n'
        
        plan_path = os.path.join(os.path.dirname(__file__), 'data', 'null-plan.gpkg')
        upload = data.Upload('id', os.path.basename(plan_path))
        
        scored, output = score.score_plan(None, None, upload, plan_path, None)
        self.assertFalse(scored.summary['Efficiency Gap'])
    
    def test_score_plan_bad_file_type(self):
        ''' An error is raised when an unknown plan file type is submitted
        '''
        plan_path = __file__
        upload = data.Upload('id', os.path.basename(plan_path), [])
        
        with self.assertRaises(RuntimeError) as error:
            score.score_plan(None, None, upload, plan_path, None)
    
    def test_score_plan_bad_file_content(self):
        ''' An error is raised when a bad plan file is submitted
        '''
        plan_path = os.path.join(os.path.dirname(__file__), 'data', 'bad-data.geojson')
        upload = data.Upload('id', os.path.basename(plan_path), [])
        
        with self.assertRaises(RuntimeError) as error:
            score.score_plan(None, None, upload, plan_path, None)
    
    def test_put_upload_index(self):
        ''' Upload index file is posted to S3
        '''
        s3, bucket, upload = unittest.mock.Mock(), unittest.mock.Mock(), unittest.mock.Mock()
        score.put_upload_index(s3, bucket, upload)
        s3.put_object.assert_called_once_with(Bucket=bucket,
            Key=upload.index_key.return_value,
            Body=upload.to_json.return_value.encode.return_value,
            ACL='public-read', ContentType='text/json')
    
    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('boto3.client')
    @unittest.mock.patch('planscore.score.calculate_gap')
    @unittest.mock.patch('planscore.score.put_upload_index')
    def test_lambda_handler(self, put_upload_index, calculate_gap, boto3_client, stdout):
        '''
        '''
        s3 = boto3_client.return_value
        s3.list_objects.return_value = {'Contents': [
            {'Key': 'uploads/sample-plan/districts/0.json'},
            {'Key': 'uploads/sample-plan/districts/1.json'}
            ]}
        
        s3.get_object.side_effect = mock_s3_get_object

        score.lambda_handler({'bucket': 'bucket-name', 'id': 'sample-plan',
            'key': 'uploads/sample-plan/upload/file.geojson'}, None)
        
        s3.list_objects.assert_called_once_with(
            Bucket='bucket-name', Prefix='uploads/sample-plan/districts')
        
        self.assertEqual(len(s3.get_object.mock_calls), 2, 'Should have asked for each district in turn')
        
        input_upload = calculate_gap.mock_calls[0][1][0]
        self.assertEqual(input_upload.id, 'sample-plan')
        self.assertEqual(len(input_upload.districts), 2)
        self.assertIn('totals', input_upload.districts[0])
        self.assertIn('totals', input_upload.districts[1])
        
        output_upload = calculate_gap.return_value
        put_upload_index.assert_called_once_with(s3, 'bucket-name', output_upload)
