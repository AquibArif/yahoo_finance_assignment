from django.shortcuts import render
from django.views.decorators.cache import cache_page

import requests
import json
import pandas
from datetime import datetime, timedelta

import logging
# This retrieves a Python logging instance (or creates it)
logger = logging.getLogger("yahoo_loggers")

def display_dashboard(request):
    # 1. Users should be able to select multiple stocks
    template = "yahoo/dashboard.html"
    stocks = ['AMRN', 'IBM', 'BTC-USD','GC=F', 'SI=F']
    
    en_dt = datetime.now()
    # default start date 3 years from today
    st_dt = en_dt - timedelta(days=3*365)
    
    context_dict = {}
    context_dict['stocks'] = stocks
    context_dict['default_start_date'] = st_dt.strftime("%Y-%m-%d")
    context_dict['default_end_date'] = en_dt.strftime("%Y-%m-%d")
    return render(request, template, context_dict)

@cache_page(60 * 15)
def compute_data(request, *args, **kwargs):
    template = "yahoo/results.html"
    # request.POST data:= <QueryDict: {u'BTC-USD-end': [u''], u'GC=F-start': [u''], u'SI=F-end': [u''], 
    # u'SI=F-start': [u''], u'IBM-end': [u''], u'IBM-start': [u''], u'favorite_stock': 
    # [u'AMRN'], u'AMRN-start': [u'2018-07-11'], u'BTC-USD-start': [u''], u'csrfmiddlewaretoken': 
    # [u'3eYgMPyiXUHjmvzYznLbLdDbwG2ntr9nEliolXt71aKEIBdqLboM6oroZ7Hv6tz3'], u'GC=F-end': [u''], u'AMRN-end': 
    # [u'2021-07-01']}>
    
    favorite_stocks =  request.POST.getlist('favorite_stock')
    
    logger.info(" Favorite stocks selected {}".format(favorite_stocks))
    
    # 2. In each stock tab, users should be able to select date range and fetch High, Low, Mean, Median stock prices
    # favorite_stocks_data conatins high, low, mean, median of stock prices
    favorite_stocks_data_dict = get_favorite_stocks_data(request, favorite_stocks)

    return render(request, template, {"stock_data":favorite_stocks_data_dict})

def get_favorite_stocks_data(request, favorite_stock):
    return_dict = {}
    for stock in favorite_stock:
        try:
            dt = datetime.now()
            
            # AMRN-start
            stock_start = stock+"-start"
            # AMRN-end
            stock_end = stock+"-end"
            start_date = request.POST.get(stock_start)
            end_date = request.POST.get(stock_end)
            
            #  if user does not select start_date
            if not end_date:
                # default start date 3 years from today
                start_date = dt - timedelta(days=3*365)
            else:
                tart_date = datetime.strptime(request.POST.get(stock_start), "%Y-%m-%d")
                
            # if user does not select end_date
            if not end_date:
                end_date = dt
            else:
                end_date = datetime.strptime(request.POST.get(stock_end), "%Y-%m-%d")
            
            response_data = send_request_to_yahoo_finance(stock, start_date, end_date)
            
            return_dict[stock] = response_data
        except Exception as e:
            logger.exception(e)
        
    return return_dict

def send_request_to_yahoo_finance(stock, start_date, end_date):
    
    url = "https://apidojo-yahoo-finance-v1.p.rapidapi.com/stock/v3/get-historical-data"
    
    logger.info("sending request to URL {}".format(url))

    querystring = {"symbol":stock,"region":"US"}

    headers = {
        'x-rapidapi-key': "01f62d082amsh2445df3cdabc3d5p16047ajsne4875531edb9",
        'x-rapidapi-host': "apidojo-yahoo-finance-v1.p.rapidapi.com"
        }

    response = requests.request("GET", url, headers=headers, params=querystring)
    
    if not response.ok:
        logger.exception("Unable to fetch data from yahoo finance")
        return
    
    # filter response based on start_date and end_date
    # convert dates to epoch datetime
    st_dt = int(start_date.strftime("%s"))
    en_dt = int(end_date.strftime("%s"))
    
    # converting text to json
    json_data = json.loads(response.content)
    price_df = pandas.DataFrame(json_data.get('prices'))
    
    filtered_df = price_df.loc[(price_df['date']>=st_dt) & (price_df['date']<= en_dt)]
    
    # filtered_df
    #         adjclose  close        date  high   low  open    volume
    # 1       4.46   4.46  1625146200  4.50  4.40  4.44   1958000
    # 2       4.38   4.38  1625059800  4.51  4.36  4.50   4114700
    # 3       4.48   4.48  1624973400  4.68  4.45  4.63   2943800
    # 4       4.64   4.64  1624887000  4.74  4.62  4.70   2000200
    # 5       4.62   4.62  1624627800  4.69  4.59  4.66   2614500

    return get_data_from_df(filtered_df)
    
# find out mean , median std, variance etc.. from given dataframe
def get_data_from_df(filtered_df):
    return_dict = {}
    try:
        return_dict['high'] = max(filtered_df['high'])
        return_dict['low'] = min(filtered_df['low'])
        return_dict['mean'] = filtered_df['close'].mean()
        return_dict['median'] = filtered_df['close'].median()
        # find variance of data
        return_dict['variance'] = filtered_df['close'].var()
        # standard deviation of close price
        return_dict['std'] = filtered_df['close'].std()
        
        
        # 5. Along with showing date-time stamps when it moved out of that range,
         # also show the time-stamp when it returned in the range for the first time.
        start_range = filtered_df['close'].mean() - filtered_df['close'].std()
        end_range = filtered_df['close'].mean() + filtered_df['close'].std()
        
        inside_range_df = filtered_df.loc[(filtered_df['close']>=start_range) & (filtered_df['close']<= end_range)]
        #get first time stock moved inside of range,  1625259580.0, removing decimal for converting to datetime
        inside_first_date = int(inside_range_df.iloc[-1]['date'])
        
        inside_first_time_dt = datetime.fromtimestamp(inside_first_date)
        
        return_dict['first_time_inside'] = inside_first_time_dt.strftime("%Y-%m-%d, %H-%M")
        
        # 4. Find the #times and time stamps where stock moved outside this range (mean + std. deviation, mean - std. deviation). 
        # The result should give only the first instance it happened
        
        cond = filtered_df['date'].isin(inside_range_df['date'])
        outside_range_df = filtered_df.drop(filtered_df[cond].index)
        #get first time stock moved outside of range,  1625259580.0, removing decimal for converting to datetime
        outside_first_date = int(outside_range_df.iloc[-1]['date'])
        
        outside_first_time_dt = datetime.fromtimestamp(outside_first_date)
        
        return_dict['first_time_outside'] = outside_first_time_dt.strftime("%Y-%m-%d, %H-%M")
    except Exception as e:
        logger.exception(e)
    
    return return_dict
    
