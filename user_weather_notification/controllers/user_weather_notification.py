# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Vishnu Vijayan KK (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import geocoder
import requests
from odoo import http
from odoo.http import request


class WeatherNotification(http.Controller):
    """
    Controller class for fetching weather details based on location.
    This class provides a controller to fetch weather information based on the
    user's location setting.
    It supports both automatic and manual location settings.
    """
    @http.route('/weather/notification/check', type='json', auth="public",
                methods=['POST'])
    def weather_notification(self):
        """
        Controller for fetching weather data
        :return: Dictionary of weather information
        :rtype: dict
        """
        weather_data = {'data': False}

        if request.env.user.api_key:
            if request.env.user.location_set == 'auto':
                try:
                    response = geocoder.ip('me')
                    if response.status_code == 200:
                        lat = round(response.latlng[0], 2)
                        lng = round(response.latlng[1], 2)
                        url = 'https://api.openweathermap.org/data/2.5' \
                              '/weather?lat=%s&lon=%s&appid=%s' % (
                                  lat, lng, request.env.user.api_key)
                        weather = requests.get(url)
                        if weather.status_code == 200:
                            weather_data = weather.json()
                except Exception:
                    pass
            elif request.env.user.location_set == 'manual':
                try:
                    url = 'https://api.openweathermap.org/data/2.5' \
                          '/weather?q=%s&appid=%s' % (
                              request.env.user.city, request.env.user.api_key)
                    city_req = requests.get(url)
                    if city_req.status_code == 200:
                        weather_data = city_req.json()
                except Exception:
                    pass
        return weather_data
