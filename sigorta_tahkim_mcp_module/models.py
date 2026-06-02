# sigorta_tahkim_mcp_module/models.py

from pydantic import BaseModel, Field
from typing import List


class SigortaTahkimSearchRequest(BaseModel):
    """Request model for searching Sigorta Tahkim Komisyonu decisions via Tavily API."""
    keywords: str = Field(..., description="Search keywords in Turkish")
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(10, ge=1, le=50, description="Results per page (1-50)")


class SigortaTahkimDecisionSummary(BaseModel):
    """Summary of a Sigorta Tahkim decision from search results."""
    title: str = Field(..., description="Decision title or journal issue info")
    document_id: str = Field(..., description="Journal issue number (e.g., '64')")
    content: str = Field(..., description="Decision summary/excerpt")
    url: str = Field("", description="Source URL")


class SigortaTahkimSearchResult(BaseModel):
    """Response model for Sigorta Tahkim decision search results."""
    decisions: List[SigortaTahkimDecisionSummary] = Field(
        default_factory=list,
        description="List of matching decisions"
    )
    total_results: int = Field(0, description="Total number of results")
    page: int = Field(1, description="Current page number")
    pageSize: int = Field(10, description="Results per page")


class SigortaTahkimDocumentMarkdown(BaseModel):
    """Sigorta Tahkim journal issue converted to Markdown format."""
    document_id: str = Field(..., description="Journal issue number")
    markdown_content: str = Field("", description="Document content in Markdown")
    page_number: int = Field(1, description="Current page number")
    total_pages: int = Field(1, description="Total number of pages")
    source_url: str = Field("", description="PDF source URL")


class SigortaTahkimSearchWithinMatch(BaseModel):
    """A single matching decision from search within a journal issue."""
    decision_header: str = Field(..., description="Decision header (date and K-number)")
    relevance_score: int = Field(0, description="Number of keyword matches")
    excerpt: str = Field("", description="Matching excerpt with context")
    body_length: int = Field(0, description="Full decision body length in chars")


class SigortaTahkimSearchWithinResult(BaseModel):
    """Response model for search within a journal issue."""
    issue_number: str = Field(..., description="Journal issue number searched")
    keyword: str = Field("", description="Search keyword used")
    total_decisions: int = Field(0, description="Total decisions in issue")
    matching_decisions: int = Field(0, description="Number of matching decisions")
    matches: List[SigortaTahkimSearchWithinMatch] = Field(
        default_factory=list,
        description="List of matching decisions sorted by relevance"
    )
