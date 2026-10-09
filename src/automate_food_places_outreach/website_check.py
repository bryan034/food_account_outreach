import argparse #pyton cli argument parser
import asyncio

from automate_food_places_outreach.services.website_fetching import (
    WebsiteFetchError,
    enrich_website,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect public website contact links")
    parser.add_argument("website_url", help="Restaurant website URL, including https://")
    arguments = parser.parse_args()
    try:
        result = asyncio.run(enrich_website(arguments.website_url))
    except WebsiteFetchError as error:
        parser.exit(status=1, message=f"Website enrichment failed: {error}\n")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
