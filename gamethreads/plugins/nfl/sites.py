import pytz

EST = pytz.timezone('US/Eastern')
CST = pytz.timezone('US/Central')
PST = pytz.timezone('US/Pacific')
MST_NODST = pytz.timezone('US/Arizona') # No DST
MST = pytz.timezone('America/Denver')
GMT = pytz.timezone('Europe/London')

sites = {
        'Gillette Stadium': [EST, 'United_States/Massachusetts/Foxborough'],
        'Georgia Dome': [EST, 'United_States/Georgia/Atlanta'],
        'Mercedes-Benz Stadium': [EST, 'United_States/Georgia/Atlanta'],
        'AT&T Stadium': [CST, 'United_States/Texas/Arlington'],
        'Arrowhead Stadium': [CST, 'United_States/Missouri/Kansas_City'],
        'Lambeau Field': [CST, 'United_States/Wisconsin/Green_Bay'],
        'NRG Stadium': [CST, 'United_States/Texas/Houston'],
        'CenturyLink Field': [PST, 'United_States/Washington/Seattle'],
        'New Era Field': [EST, 'United_States/New_York/Orchard_Park~5129951'],
        'Nissan Stadium': [CST, 'United_States/Tennessee/Nashville'],
        'Lincoln Financial Field': [EST, 'United_States/Pennsylvania/Philadelphia'],
        'Hard Rock Stadium': [EST, 'United_States/Florida/Miami_Gardens'],
        'EverBank Field': [EST, 'United_States/Florida/Jacksonville'],
        'TIAA Bank Field': [EST, 'United_States/Florida/Jacksonville'],
        'Lucas Oil Stadium': [EST, 'United_States/Indiana/Indianapolis'],
        'Bank of America Stadium': [EST, 'United_States/North_Carolina/Charlotte'],
        'FirstEnergy Stadium': [EST, 'United_States/Ohio/Cleveland'],
        'Ford Field': [EST, 'United_States/Michigan/Detroit'],
        'Levi\'s Stadium': [PST, 'United_States/California/Santa_Clara'],
        u'Levi\'s® Stadium': [PST, 'United_States/California/Santa_Clara'],
        'Raymond James Stadium': [EST, 'United_States/Florida/Tampa'],
        'Los Angeles Memorial Coliseum': [PST, 'United_States/California/Los_Angeles'],
        'MetLife Stadium': [EST, 'United_States/New_Jersey/East_Rutherford'],
        'Soldier Field': [CST, 'United_States/Illinois/Chicago'],
        'M&T Bank Stadium': [EST, 'United_States/Maryland/Baltimore'],
        'Paul Brown Stadium': [EST, 'United_States/Ohio/Cincinnati'],
        'U.S. Bank Stadium': [CST, 'United_States/Minnesota/Minneapolis'],
        'University of Phoenix Stadium': [MST_NODST, 'United_States/Arizona/Glendale'],
        'Qualcomm Stadium': [PST, 'United_States/California/San_Diego'],
        'StubHub Center': [PST, 'United_States/California/Carson'],
        'Sports Authority Field at Mile High': [MST, 'United_States/Colorado/Denver'],
        'Broncos Stadium at Mile High': [MST, 'United_States/Colorado/Denver'],
        'FedExField': [EST, 'United_States/Maryland/Landover'],
        'Oakland Coliseum': [PST, 'United_States/California/Oakland'],
        'Mercedes-Benz Superdome': [CST, 'United_States/Louisiana/New_Orleans'],
        'Heinz Field': [EST, 'United_States/Pennsylvania/Pittsburgh'],

        'Estadio Azteca': [pytz.timezone('America/Mexico_City'), 'Mexico/Distrito_Federal/Mexico_City'],
        'Estadio Azteca (Mexico City)': [pytz.timezone('America/Mexico_City'), 'Mexico/Distrito_Federal/Mexico_City'],
        'Wembley Stadium': [GMT, 'United_kingdom/England/London'],
        'Twickenham Stadium': [GMT, 'United_kingdom/England/London'],
        'Tom Benson Hall of Fame Stadium': [EST, 'United_States/Ohio/Canton'],
        'Camping World Stadium': [EST, 'United_States/Florida/Orlando'],
        }
