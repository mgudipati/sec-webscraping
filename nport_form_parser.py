# import our libraries
import requests
import pandas as pd
import os
from bs4 import BeautifulSoup


# make a function that will make the process of building a url easy.
def make_url(base_url, comp):
    url = base_url

    # add each component to the base url
    for r in comp:
        url = '{}/{}'.format(url, r)

    return url


# define a function to parse an NPORT-P form type filing
def parse_nport_form(filing_url):
    doc_dict = {}

    # request the url, and then parse the response.
    response = requests.get(filing_url)
    if response.status_code == 200:

        soup = BeautifulSoup(response.content, 'xml')

        doc_dict['asof_date'] = soup.find('repPdDate').text.strip() if soup.find('repPdDate') else ''
        doc_dict['cik_number'] = int(soup.find('cik').text) if soup.find('cik') else ''
        doc_dict['series_name'] = soup.find('seriesName').text.strip() if soup.find('seriesName') else ''
        doc_dict['total_assets'] = float(soup.find('totAssets').text) if soup.find('totAssets') else '0.0'
        doc_dict['net_assets'] = float(soup.find('netAssets').text) if soup.find('netAssets') else '0.0'

        seriesId = soup.find('seriesId').text.strip() if soup.find('seriesId') else ''
        doc_dict['series_number'] = int(seriesId[1:]) if (seriesId.startswith('S')) else ''

        tickers = soup.find_all('CLASS-CONTRACT-TICKER-SYMBOL')
        doc_dict['series_tickers'] = [ticker.text.strip() for ticker in tickers]

        invstOrSecs = soup.find_all('invstOrSec')
        doc_dict['holdings'] = []

        for invstOrSec in invstOrSecs:
            holding = {}
            holding['holding_name'] = invstOrSec.find('name').text.strip() if invstOrSec.find('name') else 'N/A'
            holding['holding_title'] = invstOrSec.find('title').text.strip() if invstOrSec.find('title') else 'N/A'
            holding['holding_share'] = float(invstOrSec.find('balance').text) if invstOrSec.find('balance') else 0.0
            holding['holding_value'] = float(invstOrSec.find('valUSD').text) if invstOrSec.find('valUSD') else 0.0
            holding['holding_type'] = invstOrSec.find('assetCat').text.strip() if invstOrSec.find('assetCat') else 'OTHER'
            doc_dict['holdings'].append(holding)

    return doc_dict


# configure the parameters to build the master index file url
base_url = r"https://www.sec.gov/Archives/edgar/daily-index"
year = '2020'
qtr = 'QTR3'
date = '20200717'

# download the master index file
file_name = 'master.{}.idx'.format(date)

# check if the file exists, so we don't need to request it again.
file = os.sep.join(['.', 'input', file_name])
if not os.path.exists(file):
    # file does not exist, download...
    file_url = make_url(base_url, [year, qtr, file_name])
    resp = requests.get(file_url)
    if resp.status_code == 200:
        print("Downloaded ", file_url)

        # we can always write the content to a file, so we don't need to request it again.
        with open(file, 'wb') as f:
            f.write(resp.content)
    else:
        print("Failed to download ", file_url)
        print(resp)
        exit(1)

# read the master index file into a pandas dataframe
df = pd.read_csv(file, delimiter='|', skiprows=5, parse_dates=['Date Filed'])
df_nport = df[df['Form Type'] == 'NPORT-P']

# parse NPORT forms
base_url = r"https://www.sec.gov/Archives"
for index, row in df_nport.iterrows():
    filing_url = make_url(base_url, [row['File Name']])
    nport_data = parse_nport_form(filing_url)
    print("Parsed ", filing_url)

    # add the filing date
    nport_data['filing_date'] = row['Date Filed'].strftime('%Y-%m-%d')

    # add the company name
    nport_data['company_name'] = row['Company Name']

    # save each NPORT form data into it's own file
    file_name = 'NPORT-P_{}_{}_{}'.format(nport_data['filing_date'],
                                          nport_data['company_name'],
                                          nport_data['series_name'])
    file = os.sep.join(['.', 'output', file_name])
    with open(file, 'w') as f:
        # write the first header row
        # As of Date	Filing Date	CIK Number	Series Number	Series name	Total Stocks Value	Total Assets	Total net Assets	Series Ticker1
        header_1 = ['As of Date',
                    'Filing Date',
                    'CIK Number',
                    'Series Number',
                    'Series name',
                    'Total Stocks Value',
                    'Total Assets',
                    'Total net Assets'
                    ] + ['Series Ticker{}'.format(i + 1) for i in range(len(nport_data['series_tickers']))]
        f.write('|'.join(header_1))
        f.write('\n')

        # write the first value row for the header
        # 2020-04-30	2020-06-26	877232	7715	Green Century Equity Fund	317251629	318112687	318798341	GCEQX
        row_1 = [nport_data['asof_date'],
                 nport_data['filing_date'],
                 str(nport_data['cik_number']),
                 str(nport_data['series_number']),
                 nport_data['series_name'],
                 '',
                 str(nport_data['total_assets']),
                 str(nport_data['net_assets'])
                 ] + [ticker for ticker in nport_data['series_tickers']]
        f.write('|'.join(row_1))
        f.write('\n')

        # write the second header row
        # Filing Classification	Holding Type	Holding Name	Holding Share	Holding Value	Holding Face Amt	Holding Number Of Contracts	Future Gain Or Loss
        header_2 = 'Filing Classification|Holding Type|Holding Name|Holding Share|Holding Value|Holding Face Amt|Holding Number Of Contracts|Future Gain Or Loss'
        f.write(header_2)
        f.write('\n')

        # write the holdings rows
        for holding in nport_data['holdings']:
            row = '{}|{}|{}|{}|{}|0|0|0'.format(holding['holding_type'],
                                                holding['holding_type'],
                                                holding['holding_name'],
                                                holding['holding_share'],
                                                holding['holding_value']
                                                )
            f.write(row)
            f.write('\n')
        print("Created ", file_name)
