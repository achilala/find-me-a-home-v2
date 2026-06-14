import pandas as pd
import pytest

from config import AppConfig


@pytest.fixture
def sample_config(tmp_path):
    return AppConfig(data_dir=tmp_path, output_path=tmp_path / "map.html")


@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {
            "LATITUDE": -36.88, "LONGITUDE": 174.73,
            "LISTING_ID": 111, "LISTING_TITLE": "House A",
            "URL": "https://example.com/1", "STREET_NUMBER": "1", "STREET": "Alpha St",
            "SUBURB": "Auckland,Auckland City,Mount Albert",
            "EXPECTED_SALE_PRICE": 1000000.0, "RATEABLE_VALUE": 900000.0,
            "BEDROOM_COUNT": 3.0, "BATHROOM_COUNT": 2.0,
            "GARAGE_PARKING_COUNT": 1.0, "LAND_AREA_IN_M2": 400.0,
            "FLOOR_AREA": 120.0, "SALE_TYPE": "Auction",
        },
        {
            "LATITUDE": -36.90, "LONGITUDE": 174.76,
            "LISTING_ID": 222, "LISTING_TITLE": "House B",
            "URL": "", "STREET_NUMBER": "2", "STREET": "Beta St",
            "SUBURB": "Auckland,Auckland City,Grey Lynn",
            "EXPECTED_SALE_PRICE": float("nan"), "RATEABLE_VALUE": float("nan"),
            "BEDROOM_COUNT": float("nan"), "BATHROOM_COUNT": float("nan"),
            "GARAGE_PARKING_COUNT": float("nan"), "LAND_AREA_IN_M2": float("nan"),
            "FLOOR_AREA": float("nan"), "SALE_TYPE": "",
        },
    ])


@pytest.fixture
def sample_geojson():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [174.70, -36.92],
                    [174.76, -36.92],
                    [174.76, -36.83],
                    [174.70, -36.83],
                    [174.70, -36.92],
                ]]
            },
            "properties": {"Hazard": "Flood Plain"},
        }]
    }


@pytest.fixture
def sample_schools():
    return [
        {
            "School_Id": 69,
            "Org_Name": "Mt Albert Grammar School",
            "Org_Type": "Secondary (Year 9-15)",
            "Definition": None,
            "Decile": 8,
            "Total": 2200,
            "Latitude": -36.888,
            "Longitude": 174.718,
            "Add1_Suburb": "Mount Albert",
        },
        {
            "School_Id": 999,
            "Org_Name": "Test Primary School",
            "Org_Type": "Contributing",
            "Definition": None,
            "Decile": 5,
            "Total": 300,
            "Latitude": -36.875,
            "Longitude": 174.725,
            "Add1_Suburb": "Mount Eden",
        },
    ]


@pytest.fixture
def sample_prefs():
    return {"12345": "interested", "67890": "uninterested"}
