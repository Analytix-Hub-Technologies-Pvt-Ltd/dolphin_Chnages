"""
Test script for Query Expansion Service

Tests the maritime query expansion functionality with various inputs.
"""

import asyncio
from services.openai_service import OpenAIService
from services.query_expansion_service import QueryExpansionService
from loguru import logger


def test_query_expansion():
    """Test query expansion with various maritime queries."""
    
    logger.info("=" * 80)
    logger.info("QUERY EXPANSION SERVICE TEST")
    logger.info("=" * 80)
    
    # Initialize services
    openai_service = OpenAIService()
    expansion_service = QueryExpansionService(openai_service, enabled=True)
    
    # Test cases
    test_queries = [
        # Single acronyms (should expand immediately)
        "SEEMP",
        "MARPOL",
        "SOLAS",
        "ISM",
        "COLREG",
        "STCW",
        
        # Short maritime terms
        "stability",
        "fire safety",
        "navigation",
        "cargo handling",
        
        # Questions
        "what is ECDIS",
        "how does radar work",
        "ship stability principles",
        
        # Already expanded (should not over-expand)
        "Ship Energy Efficiency Management Plan procedures",
    ]
    
    results = []
    
    async def _run():
        for query in test_queries:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing: '{query}'")
            logger.info(f"{'='*60}")
            
            try:
                # Test rule-based expansion first
                rule_based = expansion_service._expand_acronyms(query)
                logger.info(f"Rule-based: '{rule_based}'")
                
                # Test full LLM expansion
                expanded = await expansion_service.expand_query(
                    query,
                    chat_history=None,
                    use_llm=True
                )
                
                logger.success(f"✅ Expanded: '{expanded}'")
                
                results.append({
                    "original": query,
                    "rule_based": rule_based,
                    "llm_expanded": expanded,
                    "success": True
                })
                
            except Exception as e:
                logger.error(f"❌ Failed: {e}")
                results.append({
                    "original": query,
                    "error": str(e),
                    "success": False
                })
    
    asyncio.run(_run())
    
    # Summary
    logger.info(f"\n\n{'='*80}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*80}")
    
    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful
    
    logger.info(f"Total tests: {len(results)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    
    logger.info(f"\n{'='*80}")
    logger.info("DETAILED RESULTS")
    logger.info(f"{'='*80}\n")
    
    for i, result in enumerate(results, 1):
        if result.get("success"):
            logger.info(f"{i}. ORIGINAL: {result['original']}")
            logger.info(f"   EXPANDED: {result['llm_expanded']}")
            logger.info(f"   CHANGE:   {len(result['llm_expanded']) - len(result['original'])} chars")
            logger.info("")
        else:
            logger.error(f"{i}. FAILED: {result['original']}")
            logger.error(f"   ERROR: {result.get('error')}")
            logger.info("")
    
    # Cache stats
    stats = expansion_service.get_cache_stats()
    logger.info(f"Cache size: {stats['size']}/{stats['max_size']}")
    
    logger.info(f"\n{'='*80}")
    logger.info("TEST COMPLETE")
    logger.info(f"{'='*80}\n")
    
    return results


def test_acronym_expansion():
    """Test just the rule-based acronym expansion."""
    
    logger.info("\n" + "=" * 80)
    logger.info("TESTING RULE-BASED ACRONYM EXPANSION")
    logger.info("=" * 80)
    
    openai_service = OpenAIService()
    expansion_service = QueryExpansionService(openai_service, enabled=True)
    
    test_cases = {
        "SEEMP": "Ship Energy Efficiency Management Plan SEEMP",
        "MARPOL": "MARPOL International Convention Prevention Pollution Ships",
        "SOLAS": "SOLAS Safety Life at Sea Convention",
        "what is ISM": "ISM International Safety Management Code what is ISM",
        "STCW certification": "STCW Standards Training Certification Watchkeeping Seafarers certification",
    }
    
    all_passed = True
    
    for query, expected in test_cases.items():
        result = expansion_service._expand_acronyms(query)
        passed = (result == expected)
        
        symbol = "✅" if passed else "❌"
        logger.info(f"\n{symbol} Query: '{query}'")
        logger.info(f"   Expected: '{expected}'")
        logger.info(f"   Got:      '{result}'")
        logger.info(f"   Match:    {passed}")
        
        if not passed:
            all_passed = False
    
    logger.info(f"\n{'='*80}")
    if all_passed:
        logger.success("✅ ALL ACRONYM TESTS PASSED")
    else:
        logger.error("❌ SOME ACRONYM TESTS FAILED")
    logger.info(f"{'='*80}\n")
    
    return all_passed


if __name__ == "__main__":
    # Run tests
    test_acronym_expansion()
    test_query_expansion()

