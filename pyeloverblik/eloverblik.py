'''
Primary public module for eloverblik.dk API wrapper.
'''
from datetime import datetime
from datetime import timedelta
import json
import requests
from .models import RawResponse
from .models import TimeSeries

class Eloverblik:
    '''
    Primary exported interface for eloverblik.dk API wrapper.
    '''
    def __init__(self, refresh_token):
        self._refresh_token = refresh_token
        self._base_url = 'https://api.eloverblik.dk/CustomerApi/'

    def get_time_series(self,
                        meetering_point,
                        from_date=datetime.now()-timedelta(days=1),
                        to_date=datetime.now(),
                        aggregation='Hour'):
        '''
        Call time series API on eloverblik.dk. Defaults to yester days data.
        '''
        access_token = self._get_access_token()

        date_format = '%Y-%m-%d'
        parsed_from_date = from_date.strftime(date_format)
        parsed_to_date = to_date.strftime(date_format)
        body = "{\"meteringPoints\": {\"meteringPoint\": [\"" + meetering_point + "\"]}}"

        headers = self._create_headers(access_token)

        response = requests.post(self._base_url + f'/api/MeterData/GetTimeSeries/ \
                                    {parsed_from_date}/{parsed_to_date}/{aggregation}',
                                 data=body,
                                 headers=headers,
                                 timeout=10
                                 )

        raw_response = RawResponse()
        raw_response.status = response.status_code
        raw_response.body = response.text

        return raw_response

    def _get_access_token(self):
        url = self._base_url + 'api/Token'
        headers = {'Authorization': 'Bearer ' + self._refresh_token}

        token_response = requests.get(url, headers=headers)
        token_response.raise_for_status()

        token_json = token_response.json()

        short_token = token_json['result']

        return short_token

    def _create_headers(self, access_token):
        return {'Authorization': 'Bearer ' + access_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json'}

    def get_yesterday_parsed(self, metering_point):
        '''
        Get data for yesterday and parse it.
        '''
        raw_data = self.get_time_series(metering_point)

        if raw_data.status == 200:
            json_response = json.loads(raw_data.body)

            result_dict = self._parse_result(json_response)
            (key, value) = result_dict.popitem()
            result = value
        else:
            result = TimeSeries(raw_data.status, None, None, raw_data.body)

        return result

    def get_latest(self, metering_point):
        '''
        Get latest data. Will look for one week. 
        '''
        raw_data = self.get_time_series(metering_point, from_date=datetime.now()-timedelta(days=8))

        if raw_data.status == 200:
            json_response = json.loads(raw_data.body)

            r = self._parse_result(json_response)

            keys = list(r.keys())

            keys.sort()
            keys.reverse()

            result = r[keys[0]]
        else:
            result = TimeSeries(raw_data.status, None, None, raw_data.body)

        return result

    def _parse_result(self, result):
        '''
        Parse result from API call.
        '''
        parsed_result = {}

        if 'result' in result and len(result['result']) > 0:
            market_document = result['result'][0]['MyEnergyData_MarketDocument']
            if 'TimeSeries' in market_document and len(market_document['TimeSeries']) > 0:
                time_series = market_document['TimeSeries'][0]

                if 'Period' in time_series and len(time_series['Period']) > 0:
                    for period in time_series['Period']:                            
                        metering_data = []

                        point = period['Point']
                        for i in point:
                            metering_data.append(float(i['out_Quantity.quantity']))

                        date = datetime.strptime(period['timeInterval']['end'], '%Y-%m-%dT%H:%M:%SZ')

                        time_series = TimeSeries(200, date, metering_data)

                        parsed_result[date] = time_series
                else:
                    parsed_result['none'] = TimeSeries(404,
                                               None,
                                               None,
                                               f"Data most likely not available yet-1: {result}")
            else:
                parsed_result['none'] = TimeSeries(404,
                                  None,
                                  None,
                                  f"Data most likely not available yet-2: {result}")
        else:
            parsed_result['none'] =  TimeSeries(404, 
                              None, 
                              None, 
                              f"Data most likely not available yet-3: {result}")

        return parsed_result
