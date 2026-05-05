"""
Shared county configuration for the supplier pipeline.

Each entry defines:
  lat/lon/radius_m  — geographic centre + radius used to bias the Places API search
  bounds            — (min_lat, max_lat, min_lon, max_lon) bounding box for address validation
  signals           — postcode regex, used as a fallback when coords are unavailable

Validation logic (in order):
  1. If lat/lon available and within county bounds  → keep
  2. If lat/lon available and within London bounds  → london
  3. If lat/lon unavailable, use postcode signals regex
"""

import re

# Greater London bounding box — used to bucket borderline suppliers
LONDON_BOUNDS = (51.28, 51.70, -0.52, 0.34)  # min_lat, max_lat, min_lon, max_lon


def in_bounds(lat: float, lon: float, bounds: tuple) -> bool:
    min_lat, max_lat, min_lon, max_lon = bounds
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


COUNTY_INFO = {
    "surrey": {
        "lat": 51.31, "lon": -0.45, "radius_m": 40000,
        "bounds": (51.06, 51.52, -0.91, 0.18),
        # Postcode fallback — needed because London overlaps Surrey's lat/lon range
        # GU1-10, GU15-27: Guildford/Woking/Farnham/Camberley (GU11-14 = Aldershot = Hants)
        # KT6-8, KT10-24:  Surrey Elmbridge + wider (KT1-5, KT9 = London)
        # RH1-14:          Reigate/Redhill/Horsham border
        # TW15-20:         Staines area
        "signals": re.compile(
            r"\bSurrey\b"
            r"|GU([1-9]|10|1[5-9]|2[0-7])\b"
            r"|KT([6-8]|1[0-9]|2[0-4])\b"
            r"|RH[1-9]\b"
            r"|TW(1[5-9]|20)\b",
            re.IGNORECASE,
        ),
    },

    "west sussex": {
        "lat": 50.93, "lon": -0.46, "radius_m": 45000,
        "bounds": (50.73, 51.15, -0.99, 0.29),
        # BN5-6:    Henfield, Hassocks/Hurstpierpoint
        # BN11-18:  Worthing, Lancing, Rustington, Littlehampton, Arundel
        # BN43-45:  Shoreham-by-Sea, Steyning, Poynings area
        # RH10-17:  Crawley, Horsham, Haywards Heath, Burgess Hill
        # RH20:     Storrington/Pulborough
        # GU28-29:  Petworth, Midhurst
        # PO18-22:  Chichester, Bognor Regis
        "signals": re.compile(
            r"\bWest\s+Sussex\b"
            r"|BN([56]|1[1-8]|4[3-5])\b"
            r"|RH(1[0-7]|20)\b"
            r"|GU2[89]\b"
            r"|PO(1[89]|2[0-2])\b",
            re.IGNORECASE,
        ),
    },

    "east sussex": {
        "lat": 50.91, "lon": 0.25, "radius_m": 40000,
        "bounds": (50.74, 51.10, -0.04, 0.81),
        # BN7-10:   Lewes, Newhaven, Peacehaven
        # BN20-27:  Eastbourne, Hailsham, Seaford
        # TN5-7:    Wadhurst, Crowborough, Hartfield
        # TN19-22:  Burwash, Mayfield, Heathfield, Uckfield
        # TN31-40:  Rye, Robertsbridge, Battle, Hastings, Bexhill
        # RH18-19:  Forest Row, East Grinstead
        "signals": re.compile(
            r"\bEast\s+Sussex\b"
            r"|BN([7-9]|10|2[0-7])\b"
            r"|TN([5-7]|19|2[0-2]|3[1-9]|40)\b"
            r"|RH(1[89])\b",
            re.IGNORECASE,
        ),
    },

    "kent": {
        "lat": 51.27, "lon": 0.52, "radius_m": 55000,
        "bounds": (51.05, 51.46, 0.05, 1.46),
        # TN1-4:    Tunbridge Wells
        # TN8-18:   Edenbridge, Tonbridge, Sevenoaks, Cranbrook, Hawkhurst
        # TN23-30:  Ashford, Headcorn, Romney Marsh, Tenterden
        # ME, CT, DA, BR: Medway, Canterbury, Dartford, Bromley border
        "signals": re.compile(
            r"\bKent\b"
            r"|TN([1-4]|[89]|1[0-8]|2[3-9]|30)\b"
            r"|ME\d+|CT\d+|DA\d+|BR\d+",
            re.IGNORECASE,
        ),
    },

    "hampshire": {
        "lat": 51.06, "lon": -1.31, "radius_m": 55000,
        "bounds": (50.70, 51.27, -1.93, -0.84),
        # SO:       Southampton, Winchester, Eastleigh
        # PO1-17:   Portsmouth, Fareham, Gosport, Havant
        # GU11-14:  Aldershot, Farnborough
        # GU30-35:  Petersfield, Bordon
        # GU46-47:  Yateley, Sandhurst area
        # GU51-52:  Fleet, Hook
        # SP6-11:   Fordingbridge, Ringwood, Romsey (SP1-5 = Salisbury = Wiltshire)
        # RG21-29:  Basingstoke area
        "signals": re.compile(
            r"\bHampshire\b"
            r"|SO\d+|PO([1-9]|1[0-7])\b"
            r"|GU(11|12|13|14|3[0-5]|46|47|51|52)\b"
            r"|SP([6-9]|10|11)\b"
            r"|RG(2[1-9])\b",
            re.IGNORECASE,
        ),
    },

    "hertfordshire": {
        "lat": 51.81, "lon": -0.24, "radius_m": 40000,
        "bounds": (51.60, 51.98, -0.65, 0.25),
        # AL1-10:   St Albans, Harpenden, Hatfield, Welwyn
        # EN6-8,10-11: Potters Bar, Cuffley, Cheshunt, Broxbourne, Hoddesdon
        #               (EN1-5 and EN9 are Greater London)
        # HP1-4:    Hemel Hempstead, Berkhamsted (HP5+ = Bucks)
        # SG1-14:   Stevenage, Hitchin, Letchworth, Baldock, Hertford, Ware, WGC
        # WD3-7, WD17-25: Watford, Rickmansworth, Chorleywood, Bushey
        "signals": re.compile(
            r"\bHertfordshire\b"
            r"|AL\d+\b"
            r"|EN([6-8]|10|11)\b"
            r"|HP[1-4]\b"
            r"|SG\d+\b"
            r"|WD([3-7]|1[7-9]|2[0-5])\b",
            re.IGNORECASE,
        ),
    },

    "essex": {
        "lat": 51.74, "lon": 0.48, "radius_m": 55000,
        "bounds": (51.45, 52.05, 0.04, 1.42),
        # CM: Chelmsford, Braintree, Harlow, Epping, Bishops Stortford
        # CO: Colchester, Clacton, Sudbury
        # SS: Southend, Basildon, Wickford, Rayleigh
        # EN9: Waltham Abbey (Essex side of border)
        # CB10-11: Saffron Walden area
        "signals": re.compile(
            r"\bEssex\b"
            r"|CM\d+\b"
            r"|CO\d+\b"
            r"|SS\d+\b"
            r"|EN9\b"
            r"|CB1[01]\b",
            re.IGNORECASE,
        ),
    },

    "berkshire": {
        "lat": 51.45, "lon": -0.97, "radius_m": 40000,
        "bounds": (51.30, 51.65, -1.60, -0.55),
        # RG1-21:   Reading, Wokingham, Bracknell, Newbury, Thatcham
        # SL1-6:    Slough, Langley, Maidenhead, Windsor, Burnham
        #           (SL7-9 = Marlow/Gerrards Cross = Bucks)
        "signals": re.compile(
            r"\bBerkshire\b"
            r"|RG([1-9]|1[0-9]|20|21)\b"
            r"|SL[1-6]\b",
            re.IGNORECASE,
        ),
    },

    "buckinghamshire": {
        "lat": 51.82, "lon": -0.82, "radius_m": 45000,
        "bounds": (51.50, 52.05, -1.25, -0.40),
        # HP5-27:   Chesham, Amersham, High Wycombe, Aylesbury, Wendover,
        #           Great Missenden, Princes Risborough, Beaconsfield
        #           (HP1-4 = Hemel Hempstead = Herts)
        # MK1-19:   Milton Keynes
        # SL7, SL9: Marlow, Gerrards Cross
        "signals": re.compile(
            r"\bBuckinghamshire\b"
            r"|HP([5-9]|1[0-9]|2[0-7])\b"
            r"|MK([1-9]|1[0-9])\b"
            r"|SL[79]\b",
            re.IGNORECASE,
        ),
    },

    "oxfordshire": {
        "lat": 51.76, "lon": -1.26, "radius_m": 50000,
        "bounds": (51.44, 52.12, -1.78, -0.90),
        # OX1-49:   Oxford, Abingdon, Banbury, Bicester, Witney, Didcot,
        #           Wallingford, Henley-on-Thames, Chipping Norton, Burford
        "signals": re.compile(
            r"\bOxfordshire\b"
            r"|OX\d+\b",
            re.IGNORECASE,
        ),
    },

    "bedfordshire": {
        "lat": 52.02, "lon": -0.47, "radius_m": 35000,
        "bounds": (51.85, 52.35, -0.82, 0.05),
        # LU1-7:    Luton, Dunstable, Leighton Buzzard, Houghton Regis
        # MK40-46:  Bedford, Kempston
        # SG16-19:  Biggleswade, Sandy (Beds side of Herts border)
        "signals": re.compile(
            r"\bBedfordshire\b"
            r"|LU\d+\b"
            r"|MK4[0-6]\b"
            r"|SG1[6-9]\b",
            re.IGNORECASE,
        ),
    },

    "isle of wight": {
        "lat": 50.69, "lon": -1.30, "radius_m": 22000,
        "bounds": (50.57, 50.77, -1.62, -1.00),
        # PO30-41:  Newport, Cowes, Ryde, Sandown, Shanklin, Ventnor,
        #           Freshwater, Totland, Yarmouth
        "signals": re.compile(
            r"\bIsle\s+of\s+Wight\b"
            r"|PO(3[0-9]|40|41)\b",
            re.IGNORECASE,
        ),
    },
}

# Detects a Greater London address.
# Negative lookahead avoids matching "London Rd/Road/Street" (common Surrey street names).
LONDON_SIGNALS = re.compile(
    r"\bLondon(?!\s+R(?:oad?|d\.?)\b|\s+St(?:reet)?\b|\s+(?:Ln|Lane|Way|Ave|Cl)\b)\b"
    r"|\b(SW|SE|EC|WC|NW)[0-9]"
    r"|\bW[1-9]\b|\bW1[0-9]\b"
    r"|\bN[1-9]\b|\bN1[0-9]\b"
    r"|\bE[1-9]\b|\bE1[0-9]\b",
    re.IGNORECASE,
)
