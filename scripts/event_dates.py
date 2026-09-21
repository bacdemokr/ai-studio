"""Calendar dates shared by the brief, webpage and timetable export."""
from datetime import date, timedelta
import re


def normalize_dates(data, brief):
    parsed = {}
    for key in ('startDate', 'endDate'):
        value = data.get(key, '')
        if not isinstance(value, str):
            raise ValueError('Enter event dates as YYYY-MM-DD.')
        if value:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError('Enter event dates as YYYY-MM-DD.')
            try:
                parsed[key] = date.fromisoformat(value)
            except ValueError:
                raise ValueError('Enter a valid calendar date.') from None
    if 'endDate' in parsed and 'startDate' not in parsed:
        raise ValueError('Choose an event start date first.')
    if 'startDate' in parsed:
        parsed.setdefault('endDate', parsed['startDate'])
        days = (parsed['endDate'] - parsed['startDate']).days + 1
        if not 1 <= days <= 5:
            raise ValueError('Event dates must cover 1 to 5 days, with the end on or after the start.')
        brief['days'] = days
    brief.update({key: parsed[key].isoformat() if key in parsed else '' for key in ('startDate', 'endDate')})


def date_label(brief):
    start, end = brief.get('startDate'), brief.get('endDate')
    if not start:
        return 'Date TBC'
    a = date.fromisoformat(start)
    b = date.fromisoformat(end or start)
    if a == b:
        return a.strftime('%d %b %Y')
    if (a.year, a.month) == (b.year, b.month):
        return a.strftime('%d') + '–' + b.strftime('%d %b %Y')
    return a.strftime('%d %b %Y') + ' – ' + b.strftime('%d %b %Y')


def day_label(brief, day):
    label = 'Day ' + str(day)
    if brief.get('startDate'):
        label += ' · ' + (date.fromisoformat(brief['startDate']) + timedelta(days=day-1)).strftime('%d %b %Y')
    return label
