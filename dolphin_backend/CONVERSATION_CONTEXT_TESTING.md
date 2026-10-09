# Conversation Context & Response Variation - Testing Guide

## Overview
This guide provides test scenarios to verify the conversation context awareness and response variation feature.

## Test Scenario: Repeated "Advanced Fire Fighting" Questions

### Setup
1. Start a fresh session
2. Ask the same topic 3 times with slight variations
3. Observe how the system adapts

### Test Case 1: First Ask (Baseline)
**Query**: "advanced fire fighting?"

**Expected Behavior**:
- ✅ Comprehensive overview response
- ✅ Informative professional tone
- ✅ Covers introduction, key concepts, details, conclusion
- ✅ No acknowledgment of previous discussion
- ✅ Broad exploration follow-up questions

**Verification**:
- Check logs for: `[CONTEXT]` messages showing `times_asked=0`
- Response should be detailed and comprehensive

---

### Test Case 2: Second Ask (First Repetition)
**Query**: "ADVANCED FIRE FIGHTING"

**Expected Behavior**:
- ✅ Acknowledgment: "I covered Advanced Fire Fighting earlier..."
- ✅ Response focuses on DIFFERENT aspects (practical drills, equipment)
- ✅ Conversational helpful tone
- ✅ Offers clarifying questions at the end
- ✅ <30% content overlap with first response

**Verification**:
```bash
# Check logs for conversation context detection
grep -A5 "Repeated question detected" /path/to/logs

# Expected:
# [CONTEXT] Repeated question detected! times_asked=1, intent=general_query, strategy=practical_focus
```

**Log Indicators**:
- `[CONTEXT] Found similar query (similarity=0.XX)`
- `[CONTEXT] Topic '...' asked 1 time(s) recently. Should vary response!`
- `[CONTEXT] Response strategy: approach=practical_focus`

---

### Test Case 3: Third Ask (Frustrated Repetition)
**Query**: "can explain me adv fire fighting"

**Expected Behavior**:
- ✅ Strong acknowledgment: "I notice you're still exploring..."
- ✅ Interactive clarification approach
- ✅ Collaborative empathetic tone
- ✅ Explicit options menu for user to choose direction:
  ```
  I notice you're asking about Advanced Fire Fighting again. I can help you explore:
  1. 🔍 **Practical Applications** - ...
  2. ⚙️ **Technical Details** - ...
  3. 📋 **Procedures** - ...
  4. 🎯 **Examples** - ...
  
  Which aspect would you like to focus on?
  ```
- ✅ Response content significantly different from first two responses

**Verification**:
```bash
# Check for frustrated repetition detection
grep "intent=frustrated_repetition" /path/to/logs

# Expected:
# [CONTEXT] Detected frustrated_repetition (asked 2 times)
# [CONTEXT] Repeated question detected! times_asked=2, intent=frustrated_repetition, strategy=interactive_clarification
```

---

## Test Scenario: Intent Detection

### Test Case 4: Simplification Intent
**Query**: "explain advanced fire fighting in simple terms"

**Expected Behavior**:
- ✅ Detected intent: `simplification`
- ✅ Clear, accessible language
- ✅ Avoids heavy jargon
- ✅ Uses analogies and simple examples

**Log Check**:
```
[CONTEXT] Response strategy: approach=simplified_explanation, tone=clear_accessible
```

---

### Test Case 5: More Detail Intent
**Query**: "I need more details about advanced fire fighting procedures"

**Expected Behavior**:
- ✅ Detected intent: `more_detail`
- ✅ Comprehensive technical depth
- ✅ Detailed specifications
- ✅ In-depth explanations

**Log Check**:
```
[CONTEXT] Response strategy: approach=comprehensive_deep_dive, tone=detailed_technical
```

---

### Test Case 6: Practical Intent
**Query**: "how to perform advanced fire fighting drills"

**Expected Behavior**:
- ✅ Detected intent: `practical`
- ✅ Step-by-step procedures
- ✅ Instructional tone
- ✅ Emphasis on actions and operations

**Log Check**:
```
[CONTEXT] Response strategy: approach=step_by_step_practical, tone=instructional_clear
```

---

### Test Case 7: Examples Intent
**Query**: "give me examples of advanced fire fighting scenarios"

**Expected Behavior**:
- ✅ Detected intent: `examples`
- ✅ Scenario-based response
- ✅ Real-world case studies
- ✅ Illustrative storytelling

**Log Check**:
```
[CONTEXT] Response strategy: approach=scenario_based, tone=illustrative_engaging
```

---

## Response Variation Metrics

### How to Measure Response Variation

**Method 1: Manual Comparison**
1. Copy Response 1 text
2. Copy Response 2 text
3. Use online text comparison tool (e.g., diffchecker.com)
4. Verify <70% similarity (i.e., <30% overlap)

**Method 2: Structural Comparison**
Compare response structures:
- Response 1: Introduction → Key Areas → Conclusion
- Response 2: Acknowledgment → Practical Focus → Examples → Clarification
- Response 3: Acknowledge Repetition → Interactive Options → Focused Detail

**Success Criteria**:
- ✅ Different opening sentences
- ✅ Different section structures
- ✅ Different emphasis (theory vs practice vs examples)
- ✅ Different follow-up questions

---

## Expected Log Output

### First Query (times_asked=0):
```
[QUERY NODE] Formatted chunks_content length: 2543 chars, from 3 chunks...
[QUERY NODE] Final prompt length: 4821 chars
```

### Second Query (times_asked=1):
```
[CONTEXT] Found similar query (similarity=0.87): 'advanced fire fighting' vs 'ADVANCED FIRE FIGHTING'
[CONTEXT] Topic 'ADVANCED FIRE FIGHTING' asked 1 time(s) recently. Should vary response!
[CONTEXT] Response strategy: approach=practical_focus, tone=conversational_helpful, times_asked=1, intent=general_query
[CONTEXT] Repeated question detected! times_asked=1, intent=general_query, strategy=practical_focus
```

### Third Query (times_asked=2):
```
[CONTEXT] Found similar query (similarity=0.92): 'advanced fire fighting' vs 'adv fire fighting'
[CONTEXT] Found similar query (similarity=0.89): 'ADVANCED FIRE FIGHTING' vs 'adv fire fighting'
[CONTEXT] Topic 'adv fire fighting' asked 2 time(s) recently. Should vary response!
[CONTEXT] Detected frustrated_repetition (asked 2 times)
[CONTEXT] Response strategy: approach=interactive_clarification, tone=collaborative_empathetic, times_asked=2, intent=frustrated_repetition
[CONTEXT] Repeated question detected! times_asked=2, intent=frustrated_repetition, strategy=interactive_clarification
```

---

## Debugging Commands

### Check if Conversation Context is Active:
```bash
# Look for ConversationContextService initialization
grep "ConversationContextService initialized" /path/to/logs

# Expected output:
# ConversationContextService initialized (similarity_threshold=0.65)
```

### Monitor Repeated Question Detection:
```bash
# Real-time monitoring
tail -f /path/to/logs | grep --color=auto "\[CONTEXT\]"
```

### Check Response Strategy Changes:
```bash
# Search for strategy variations
grep "Response strategy: approach=" /path/to/logs | sort | uniq -c
```

---

## Success Criteria Summary

### Feature is Working Correctly When:
1. ✅ **Detection**: System logs show repeated questions are detected
2. ✅ **Variation**: Responses have <30% text overlap
3. ✅ **Acknowledgment**: Second+ responses acknowledge previous discussion
4. ✅ **Intent**: User intent is correctly detected and applied
5. ✅ **Options**: Follow-up options are presented for 2+ repetitions
6. ✅ **Tone**: Tone adapts based on repetition count and intent

### Red Flags (Indicates Issues):
- ❌ No `[CONTEXT]` logs for repeated questions
- ❌ >70% text overlap between responses
- ❌ No acknowledgment on second+ ask
- ❌ Same follow-up questions every time
- ❌ No interactive options on third ask
- ❌ Errors mentioning `ConversationContextService`

---

## Rollback Plan

If issues are detected:
1. Check `services/conversation_context_service.py` for errors
2. Verify `graph/query_node.py` integration is correct
3. Check logs for exceptions
4. If critical: Temporarily disable by setting `similarity_threshold=1.0` (effectively disables detection)
5. Create hotfix commit with detailed issue description

---

## Performance Considerations

### Overhead Added:
- **Similarity calculation**: ~1-5ms per query (negligible)
- **Context checking**: Iterates over last 10 history entries (~<1ms)
- **Strategy determination**: Simple logic (~<1ms)

**Total overhead**: <10ms per query (acceptable for improved UX)

### Memory Impact:
- Stores conversation history in state (already done)
- No additional caching or storage needed
- Minimal memory footprint

---

## Client Communication

### How to Present to Client:

**Before**:
- User asks "Advanced Fire Fighting" → Gets detailed answer
- User asks "ADVANCED FIRE FIGHTING" → Gets **same** answer (frustrating)
- User asks again → Still **same** answer (user gives up)

**After**:
- User asks "Advanced Fire Fighting" → Gets comprehensive overview
- User asks "ADVANCED FIRE FIGHTING" → System acknowledges, varies response, focuses on practical aspects
- User asks again → System offers interactive menu to clarify what specific aspect they need

**Result**: 
- Improved user satisfaction
- Reduced repeated questions (user gets what they need faster)
- More engaging conversation flow
- Better learning outcomes

---

## Next Steps After Testing

1. ✅ Verify all test cases pass
2. ✅ Monitor production logs for 24 hours
3. ✅ Collect user feedback
4. ✅ Fine-tune similarity threshold if needed (currently 0.65)
5. ✅ Adjust response strategies based on usage patterns
