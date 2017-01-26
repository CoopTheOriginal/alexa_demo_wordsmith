import csv, json, os
import requests
from flask_ask import statement, question
from flask import render_template, session


def pipe(data, *functions):
    """Passes data through first function, then passes result of each
    function to the next"""
    for func in functions:
        data = func(data)
    return data


def __delta_calc(number_a, number_b):
    if number_b == 0 and number_a > 0: return 1
    elif number_b == 0 and number_a == 0: return 0
    elif number_b == 0 and number_a < 0: return -1
    return (number_a - number_b) / abs(float(number_b))


def __profit_change(data_set, category, dates):
    """Finds the profit change given a data set, and a category for which
    to break out the period over period profit change. Returns a dictionary
    containing the top category's {prev_year: gross profit,
    current_year: gross profit, profit_change}"""

    def year_breakout(category):
        """Breaks out a data set into two dictionaries by two latest periods"""
        categories = set([x[category] for x in data_set])
        years_dict = {str(dates[0]): dict([(x, 0) for x in categories]),
                      str(dates[1]): dict([(x, 0) for x in categories])}
        for x in data_set:
            years_dict[str(dates[0])][x[category]] += x[str(dates[0])]
            years_dict[str(dates[1])][x[category]] += x[str(dates[1])]
        return years_dict

    def category_profit_pct(info_dict):
        """Takes in dictionary of two years worth of data and appends to that
        dict a sorted tuple list of deltas for each category"""
        info_dict['deltas'] = sorted([(key, __delta_calc(info_dict[str(dates[1])][key], num))
                                      for key, num in info_dict[str(dates[0])].items()],
                                     key=lambda x:x[1], reverse=True)
        return info_dict

    info_dict = pipe(category, year_breakout, category_profit_pct)

    top_category = info_dict['deltas'][0]
    worst_category = info_dict['deltas'][-1]
    return {'category': top_category[0],
            'profit_change': top_category[1],
            'prev_profit': round(info_dict[str(dates[-2])][top_category[0]], -3),
            'current_profit': round(info_dict[str(dates[-1])][top_category[0]], -3),
            'worst_category': worst_category[0],
            'worst_profit_change': worst_category[1]}


def __wordsmith(calcs):
    """Hits wordsmith api to append 'content' key (with narrative)
    to passed info_dict."""
    url = 'https://api.automatedinsights.com/v1/projects/spotfire/templates/finance-geography-alexa/outputs'

    headers = {'Authorization': 'Bearer ' + os.environ['AI_API'],
               'Content-Type': 'application/json',
               'User-Agent': 'Hackathon'}

    data = json.dumps({'data': calcs})
    response = requests.post(url, headers=headers, data=data)

    try:
        if 'errors' in response.json().keys():
            return response.json()['errors'][0]['detail']
        else:
            return response.json()['data']['content']
    except:
        if response.status_code == 401:
            return 'Invalid API Key'
        else:
            return response.status_code


def __get_calcs(state):

    def num_transform(a_string):
    	if a_string == '-' or a_string.count('-') > 1:
            return 0
    	try:
    		a_string = a_string.replace(',', '').replace('$', '')
    		return float(a_string)
    	except:
    		return a_string

    def dict_transform(a_dict):
        for key, value in a_dict.items():
            a_dict[key] = num_transform(value)
        return a_dict

    stateDict = [dict_transform(x) for x in csv.DictReader(open('raw_data.csv')) if x['State'] == state]
    allRegionDict = [dict_transform(x) for x in csv.DictReader(open('raw_data_region.csv'))]
    allBusinessUnitDict = [dict_transform(x) for x in csv.DictReader(open('raw_data_business_unit.csv'))]
    allProductGroupDict = [dict_transform(x) for x in csv.DictReader(open('raw_data_product.csv'))]
    dates = ['2008', '2009']



    top_state_profit_dict = __profit_change(stateDict, 'State', dates)

    top_state_list = filter(lambda x: x['State'] == top_state_profit_dict['category'], stateDict)

    top_bu_profit_dict = __profit_change(stateDict, 'Business Unit', dates)
    top_prod_profit_dict = __profit_change(stateDict, 'Product Group', dates)


    all_top_region_profit_dict = __profit_change(allRegionDict, 'Region', dates)
    all_top_bu_profit_dict = __profit_change(allBusinessUnitDict, 'Business Unit', dates)
    all_top_prod_profit_dict = __profit_change(allProductGroupDict, 'Product Group', dates)

    return {'timeframe': 'year',
            'state_count': 1,
            'region_count': 1,
            'state_top_profit_change': top_state_profit_dict['category'],
            'state_top_profit_change_value': top_state_profit_dict['profit_change'],
            'state_top_profit_change_profit_current': top_state_profit_dict['current_profit'],
            'state_top_profit_change_profit_prev': top_state_profit_dict['prev_profit'],
            'state_top_profit_change_top_bu': top_bu_profit_dict['category'],
            'state_top_profit_change_top_bu_value': top_bu_profit_dict['profit_change'],
            'state_top_profit_change_top_bu_current': top_bu_profit_dict['current_profit'],
            'state_top_profit_change_bot_bu': top_bu_profit_dict['worst_category'],
            'state_top_profit_change_bot_bu_value': top_bu_profit_dict['worst_profit_change'],
            'state_top_profit_change_top_prod': top_prod_profit_dict['category'],
            'state_top_profit_change_top_prod_value': top_prod_profit_dict['profit_change'],
            'state_top_profit_change_top_prod_current': top_prod_profit_dict['current_profit'],
            'state_top_profit_change_bot_prod': top_prod_profit_dict['worst_category'],
            'state_top_profit_change_bot_prod_value': top_prod_profit_dict['worst_profit_change'],
            'state_top_profit_change_region': stateDict[0]['Region'],
            'region_top_profit_change': all_top_region_profit_dict['category'],
            'region_top_profit_change_value': all_top_region_profit_dict['profit_change'],
            'bu_top_profit_change': all_top_bu_profit_dict['category'],
            'bu_top_profit_change_value': all_top_bu_profit_dict['profit_change'],
            'prod_top_profit_change': all_top_prod_profit_dict['category'],
            'prod_top_profit_change_value': all_top_prod_profit_dict['profit_change']}


def __send_email(info_dict):
    def build_html_version(info_dict):
        clean_link = info_dict['url'].replace("'", '&#39;').replace('"', '&quot;')

        greeting = 'Hello,<br><p>Below is the report you requested from Alexa.</p>'
        closing = '<p>Have a great day!<br>Your Friends at TIBCO Spotfire</p><br>'
        header = '<h2>Summary for {}</h2>'.format(info_dict['state'])
        content = '<p>{}</p>'.format(info_dict['narrative'])
        link = '<p><a href="{}">Click here to view an in-depth summary report for {}.</a></p><br>'.format(clean_link, info_dict['state'])
        closer = '<p><img src="http://spotfire.tibco.com/assets/blt319e5175d30d41b2/TIBCO-Spotfire-Logo.png"></p>'
        return ''.join([greeting, closing, header, content, link, closer])

    email_subject = 'Spotfire Analysis for: ' + info_dict['state']
    email_text = info_dict['narrative'] + '\n' + 'View your Spotfire dashboard here: ' + info_dict['url']
    url = 'https://api.mailgun.net/v3/sandbox7df9a80a5985432b8d4050cd52360101.mailgun.org/messages'
    auth = ('api', os.environ['MAILGUN'])
    data = {'to': os.envrion['TO_EMAIL'],
            'from': os.envrion['FROM_EMAIL'],
            'subject': email_subject,
            'text': email_text,
            'html': build_html_version(info_dict)}
    r = requests.post(url=url, auth=auth, data=data)
    return r.json()


def __build_url(state):
    """Given a state, build URL"""
    return "http://54.197.21.167/spotfire/wp/OpenAnalysis?file="\
           "/Hackathon/Master%20Wordsmith%20Demo2&configuration"\
           "Block=aiProfitTrigger=9998;SetPage(pageTitle=\"Prof"\
           "itability by Geography\");SetMarking(markingName=\""\
           "MapMarking\",tableName=\"Superstore_Sales_r\",where"\
           "Clause=\"State='" + state + "'\",operation=Replace);"


def __email_narrative(session_dict):
    """Emails passed narrative to person"""
    __send_email(session_dict)
    session.attributes = {}
    return question(render_template('confirmation1'))


def __get_narrative(state):
    calcs = __get_calcs(state)
    return __wordsmith(calcs)


def __good_state_check(state):
    state_list = set([x['State'] for x in csv.DictReader(open("raw_data.csv"))])
    if state in state_list: return True
    else: return False
