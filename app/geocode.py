"""
Geocoding helpers — shared by main.py and request_routes.py.
"""

import json
import urllib.error
import urllib.parse
import urllib.request


def geocode_uk_postcode(postcode: str) -> tuple[float, float]:
    clean = ''.join((postcode or '').upper().split())
    if not clean:
        raise ValueError('Missing postcode')

    url = f"https://api.postcodes.io/postcodes/{urllib.parse.quote(clean)}"
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError('Postcode lookup service is unavailable right now.') from exc

    if payload.get('status') != 200 or not payload.get('result'):
        raise ValueError('Postcode not found. Please check and try again.')

    result = payload['result']
    return float(result['latitude']), float(result['longitude'])


def geocode_uk_address(address: str) -> tuple[float, float]:
    query = (address or '').strip()
    if not query:
        raise ValueError('Missing address')

    params = urllib.parse.urlencode({
        'q': f'{query}, UK',
        'format': 'jsonv2',
        'limit': 1,
    })
    req = urllib.request.Request(
        f'https://nominatim.openstreetmap.org/search?{params}',
        headers={'User-Agent': 'Hedera-TradeRoot/1.0'},
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            results = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError('Address lookup service is unavailable right now.') from exc

    if not results:
        raise ValueError('Address not found. Please check and try again.')

    first = results[0]
    return float(first['lat']), float(first['lon'])


def resolve_coordinates(address: str | None, postcode: str | None) -> tuple[float | None, float | None]:
    """Try address geocoding first, fall back to postcode, return (None, None) if both fail."""
    if address:
        try:
            return geocode_uk_address(address)
        except ValueError:
            pass
        except RuntimeError:
            pass
    if postcode:
        try:
            return geocode_uk_postcode(postcode)
        except (ValueError, RuntimeError):
            pass
    return None, None
