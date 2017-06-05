"""This modlule contains data definitions for Knoema client"""

from datetime import datetime
import pandas
import apy_definitions as definition

class DataReader(object):
    """This class read data from Knoema and transform it to pandas frame"""

    def __init__(self, client, dataset, dim_values):
        self.client = client
        self.dataset = dataset
        self.dim_values = dim_values

    def _get_dim_members(self, dim, splited_values):

        members = []
        for value in splited_values:
            if not value:
                raise ValueError('Selection for dimension {} is empty'.format(dim.name))

            member = dim.findmember_by_id(value)
            if not member:
                member = dim.findmember_by_name(value)

            if member:
                members.append(member.key)

        return members

    def _create_pivot_request(self):

        pivotreq = definition.PivotRequest(self.dataset.id)

        time_range = None
        for name, value in self.dim_values.items():
            if definition.isequal_strings_ignorecase(name, 'timerange'):
                time_range = value
                continue

            splited_values = value.split(';')
            if definition.isequal_strings_ignorecase(name, 'frequency'):
                pivotreq.frequencies = splited_values
                continue

            dim = self.dataset.find_dimension_by_name(name)
            if not dim:
                raise ValueError('Dimension with name {} is not found'.
                                 format(name))

            dim = self.client.get_dimension(self.dataset.id, dim.id)
            members = self._get_dim_members(dim, splited_values)
            if not members:
                raise ValueError('Selection for dimension {} is empty'.format(dim.name))

            pivotreq.stub.append(definition.PivotItem(dim.id, members))

        if time_range:
            pivotreq.header.append(definition.PivotTimeItem('Time', [time_range], 'range'))
        else:
            pivotreq.header.append(definition.PivotTimeItem('Time', [], 'AllData'))

        return pivotreq

    def _get_series_name(self, series_point):
        names = []
        for dim in self.dataset.dimensions:
            names.append(series_point[dim.id])
        names.append(series_point['Frequency'])
        return ' - '.join(names)

    def _get_series(self, resp):
        series = {}
        for series_point in resp.tuples:
            val = series_point['Value']
            if not val:
                continue
                
            series_name = self._get_series_name(series_point)
            if series_name not in series:
                series[series_name] = KnoemaTimeSeries(series_name)

            curr_date_val = series_point['Time']
            try:
                curr_date_val = datetime.strptime(series_point['Time'], '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                pass

            series[series_name].add_value(series_point['Value'], curr_date_val)

        return series

    def get_pandasframe(self):
        """The method loads data from dataset"""

        pivotreq = self._create_pivot_request()
        pitvotresp = self.client.get_data(pivotreq)

        series = self._get_series(pitvotresp)
        pandas_series = {}
        for series_name, series_content in series.items():
            pandas_series[series_name] = series_content.get_pandas_series()

        pandas_data_frame = pandas.DataFrame(pandas_series)
        pandas_data_frame.sort_index()
        return pandas_data_frame


class KnoemaTimeSeries(object):
    """This class combines values and date points for one time series"""

    def __init__(self, name):
        self.name = name
        self.values = []
        self.dates = []

    def add_value(self, value, date_point):
        """The function is addeing new value to provied date. If date does not exist"""
        if date_point not in self.dates:
            self.values.append(value)
            self.dates.append(date_point)

    def get_pandas_series(self):
        """The function creates pandas series based on dates and values"""
        return pandas.Series(self.values, self.dates, name=self.name)
