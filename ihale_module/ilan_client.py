#!/usr/bin/env python3
"""
İlan.gov.tr API client for Turkish government announcements and notifications
"""

import httpx
import ssl
from typing import Dict, Any, Optional, List
from io import BytesIO
from markitdown import MarkItDown
from ihale_models import IlanSearchResponse, IlanAd, IlanAdDetail


class IlanClient:
    """Client for ilan.gov.tr API"""

    def __init__(self):
        self.base_url = "https://www.ilan.gov.tr"
        self.search_endpoint = "/api/api/services/app/Ad/AdsByFilter"
        self.detail_endpoint = "/api/api/services/app/AdDetail/GetAdDetail"

        # Common headers for all requests
        self.headers = {
            'accept': 'text/plain',
            'accept-language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/json-patch+json',
            'expires': 'Sat, 01 Jan 2000 00:00:00 GMT',
            'origin': 'https://www.ilan.gov.tr',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://www.ilan.gov.tr/ilan/tum-ilanlar',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'x-request-origin': 'IGT-UI',
            'x-requested-with': 'XMLHttpRequest'
        }

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context that supports standard protocols"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    async def _make_request(self, endpoint: str, params: dict) -> dict:
        """Make an API request to ilan.gov.tr"""
        ssl_context = self._create_ssl_context()

        async with httpx.AsyncClient(
            timeout=30.0,
            verify=ssl_context,
            http2=False,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        ) as client:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                json=params,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def search_ads(
        self,
        search_text: str = "",
        skip_count: int = 0,
        max_result_count: int = 12,
        search_in_title: bool = False,
        search_in_content: bool = False,
        city_id: Optional[int] = None,
        city: Optional[str] = None,
        category: Optional[str] = None,
        ad_type: Optional[str] = None,
        ad_type_id: Optional[int] = None,  # ats parameter (2=İcra, 3=İhale, 4=Tebligat, 5=Personel)
        ad_source: Optional[str] = None,  # as parameter (UYAP=E-SATIŞ, BIK=Basın İlan Kurumu)
        publish_date_min: Optional[str] = None,
        publish_date_max: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        current_page: int = 1
    ) -> Dict[str, Any]:
        """Search for advertisements on ilan.gov.tr"""

        # Build search keys based on search type and filters
        keys = {}

        # Search text handling
        if search_text:
            if search_in_title:
                keys["t"] = [search_text]  # Title search
            elif search_in_content:
                keys["c"] = [search_text]  # Content search
            else:
                keys["q"] = [search_text]  # General search (default)

        # City filter - prioritize city_id over city name
        if city_id is not None:
            keys["aci"] = [city_id]
        elif city:
            keys["city"] = [city]

        # Other filters
        if category:
            keys["category"] = [category]
        if ad_type:
            keys["adType"] = [ad_type]

        # Ad type ID filter (ats parameter)
        if ad_type_id is not None:
            keys["ats"] = [ad_type_id]

        # Ad source filter (as parameter)
        if ad_source:
            keys["as"] = [ad_source]

        # Date filters (DD.MM.YYYY format)
        if publish_date_min:
            keys["ppdmin"] = [publish_date_min]
        if publish_date_max:
            keys["ppdmax"] = [publish_date_max]

        # Price filters
        if price_min is not None:
            keys["prmin"] = [str(price_min)]
        if price_max is not None:
            keys["prmax"] = [str(price_max)]

        # Page handling - calculate skipCount from currentPage if not explicitly set
        if current_page > 1:
            keys["currentPage"] = [current_page]
            if skip_count == 0:
                skip_count = (current_page - 1) * max_result_count

        # Build API request payload
        api_params = {
            "keys": keys,
            "skipCount": skip_count,
            "maxResultCount": max_result_count
        }

        try:
            # Make API request
            response_data = await self._make_request(self.search_endpoint, api_params)

            # Extract the result section
            result = response_data.get("result", {})

            # Parse and format the response
            ads = result.get("ads", [])
            categories = result.get("categories", [])
            city_counts = result.get("cityCounts", [])
            num_found = result.get("numFound", 0)

            # Format each ad for better readability
            formatted_ads = []
            for ad in ads:
                # Extract key-value pairs from adTypeFilters
                filter_info = {}
                for filter_item in ad.get("adTypeFilters", []):
                    key = filter_item.get("key", "")
                    value = filter_item.get("value", "")
                    filter_info[key] = value

                formatted_ad = {
                    "id": ad.get("id"),
                    "ad_no": ad.get("adNo"),
                    "advertiser_name": ad.get("advertiserName"),
                    "title": ad.get("title"),
                    "city": ad.get("addressCityName"),
                    "county": ad.get("addressCountyName"),
                    "publish_date": ad.get("publishStartDate"),
                    "url": ad.get("urlStr"),
                    "full_url": f"https://www.ilan.gov.tr{ad.get('urlStr', '')}",
                    "ad_source": ad.get("adSourceName"),
                    "filter_info": filter_info,
                    "is_archived": ad.get("isArchived", False)
                }
                formatted_ads.append(formatted_ad)

            # Format categories
            formatted_categories = []
            for category in categories:
                formatted_categories.append({
                    "id": category.get("taxId"),
                    "name": category.get("name"),
                    "slug": category.get("slug"),
                    "count": category.get("count"),
                    "order": category.get("orderNo")
                })

            # Format city counts
            formatted_cities = []
            for city in city_counts:
                formatted_cities.append({
                    "id": city.get("id"),
                    "name": city.get("key"),
                    "count": city.get("count")
                })

            return {
                "ads": formatted_ads,
                "categories": formatted_categories,
                "city_counts": formatted_cities,
                "total_found": num_found,
                "returned_count": len(formatted_ads),
                "search_params": {
                    "search_text": search_text,
                    "search_in_title": search_in_title,
                    "search_in_content": search_in_content,
                    "skip_count": skip_count,
                    "max_result_count": max_result_count,
                    "city_id": city_id,
                    "city": city,
                    "category": category,
                    "ad_type": ad_type,
                    "ad_type_id": ad_type_id,
                    "ad_source": ad_source,
                    "publish_date_min": publish_date_min,
                    "publish_date_max": publish_date_max,
                    "price_min": price_min,
                    "price_max": price_max,
                    "current_page": current_page
                }
            }

        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Request failed",
                "message": str(e)
            }

    async def get_ad_detail(
        self,
        ad_id: str
    ) -> Dict[str, Any]:
        """Get detailed information for a specific advertisement"""

        ssl_context = self._create_ssl_context()

        try:
            # Make GET request with query parameter
            async with httpx.AsyncClient(
                timeout=30.0,
                verify=ssl_context,
                http2=False,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            ) as client:
                response = await client.get(
                    f"{self.base_url}{self.detail_endpoint}",
                    params={"id": ad_id},
                    headers=self.headers
                )
                response.raise_for_status()
                response_data = response.json()

            # Check if successful
            if not response_data.get("success", False):
                return {
                    "error": "API returned unsuccessful response",
                    "message": response_data.get("error", "Unknown error")
                }

            # Extract result
            result = response_data.get("result", {})

            if not result:
                return {
                    "error": "No detail found",
                    "ad_id": ad_id
                }

            # Extract HTML content
            html_content = result.get("content", "")

            # Convert HTML to Markdown
            markdown_content = None
            if html_content:
                try:
                    # Initialize markdown converter
                    markitdown = MarkItDown()
                    # Create BytesIO from HTML content
                    html_bytes = BytesIO(html_content.encode('utf-8'))
                    conversion_result = markitdown.convert_stream(html_bytes, file_extension=".html")
                    markdown_content = conversion_result.text_content if conversion_result else None
                except Exception as e:
                    print(f"Warning: Failed to convert HTML to markdown: {e}")
                    markdown_content = None

            # Format categories
            categories = []
            for cat in result.get("categories", []):
                categories.append({
                    "id": cat.get("taxId"),
                    "name": cat.get("name"),
                    "slug": cat.get("slug")
                })

            # Format filters
            ad_type_filters = []
            for filter_item in result.get("adTypeFilters", []):
                ad_type_filters.append({
                    "key": filter_item.get("key"),
                    "value": filter_item.get("value")
                })

            # Build response
            return {
                "ad_detail": {
                    "id": result.get("id"),
                    "ad_no": result.get("adNo"),
                    "title": result.get("title"),
                    "content_html": html_content,
                    "content_markdown": markdown_content,
                    "city": result.get("addressCityName"),
                    "county": result.get("addressCountyName"),
                    "advertiser": {
                        "name": result.get("advertiserName"),
                        "code": result.get("advertiserCode"),
                        "logo": result.get("advertiserLogo")
                    },
                    "source": {
                        "name": result.get("adSourceName"),
                        "code": result.get("adSourceCode"),
                        "logo": result.get("adSourceLogoPath")
                    },
                    "url": result.get("urlStr"),
                    "full_url": f"https://www.ilan.gov.tr{result.get('urlStr', '')}",
                    "categories": categories,
                    "filters": ad_type_filters,
                    "statistics": {
                        "hit_count": result.get("hitCount", 0),
                        "is_archived": result.get("isArchived", False),
                        "is_bik": result.get("isBikAd", False)
                    }
                },
                "success": True
            }

        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e),
                "ad_id": ad_id
            }
        except Exception as e:
            return {
                "error": "Request failed",
                "message": str(e),
                "ad_id": ad_id
            }