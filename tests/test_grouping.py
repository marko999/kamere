def test_all_crossings_have_country_border():
    from src.config import CROSSINGS
    from src.database import _BORDER_MAP
    for name in CROSSINGS:
        assert name in _BORDER_MAP


def test_country_groups_cover_all_borders():
    from src.database import _BORDER_MAP
    ALL_BORDERS = ['SRB-HUN', 'SRB-HRV', 'SRB-BIH', 'HRV-BIH', 'SRB-ROU', 'SRB-BGR', 'SRB-MNE', 'SRB-MKD', 'HRV-SLO']
    for border in _BORDER_MAP.values():
        assert border in ALL_BORDERS
