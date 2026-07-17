import { useState, useEffect, useRef, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { api } from '../services/apiClient';
import LoadingSpinner from '../components/LoadingSpinner';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import './QA.css';

// The AI is instructed to emit $...$ / $$...$$ math delimiters (what remark-math
// expects), but LLMs sometimes fall back to \( \) / \[ \] regardless of the prompt.
// Normalize those to $ delimiters so KaTeX still renders the math.
function normalizeMathDelimiters(text) {
  if (!text) return text;
  return text
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, expr) => `$$${expr}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, expr) => `$${expr}$`);
}

function QA() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [conversation, setConversation] = useState([]);
  const [historyConversation, setHistoryConversation] = useState([]);
  const preloadSentRef = useRef(false); // Use ref to track if preload was sent (persists across re-renders)
  const historyLoadedRef = useRef(false); // Track if history has been loaded
  const conversationEndRef = useRef(null); // Ref for scrolling to bottom

  const { success, error: showError } = useToast();
  
  // Fetch conversation history on mount
  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['conversation-history', user?.id],
    queryFn: () => {
      console.log('[QA] Fetching conversation history for user:', user.id);
      return api.getConversationHistory(user.id, 10, 24).then(res => {
        console.log('[QA] Conversation history response:', res.data);
        return res.data;
      });
    },
    enabled: !!user?.id && !historyLoadedRef.current,
    retry: false,
    onError: (error) => {
      console.log('[QA] Conversation history API error (expected in dev):', error);
    }
  });
  
  // Load conversation history into a separate history state when it's fetched
  // (kept apart from `conversation` so history arriving can never look like a live answer arriving)
  useEffect(() => {
    if (historyData?.data?.interactions && !historyLoadedRef.current) {
      console.log('[QA] Loading conversation history into state');
      const interactions = historyData.data.interactions;
      const loadedConversation = [];

      // Convert API format to conversation format
      for (const interaction of interactions) {
        loadedConversation.push({
          type: 'user',
          content: interaction.query || interaction.question || ''
        });
        loadedConversation.push({
          type: 'assistant',
          content: interaction.answer || interaction.response || '',
          confidence: interaction.confidence || 'Medium'
        });
      }

      if (loadedConversation.length > 0) {
        setHistoryConversation(loadedConversation);
        historyLoadedRef.current = true;
        console.log('[QA] Loaded', loadedConversation.length / 2, 'previous interactions');
      }
    }
  }, [historyData]);

  // Scroll to bottom when conversation updates or component mounts
  useEffect(() => {
    if (conversationEndRef.current) {
      // Small delay to ensure DOM has updated
      setTimeout(() => {
        conversationEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }, 100);
    }
  }, [conversation, historyConversation]);
  
  // Check for preloaded query from Practice page
  const preloadedQuery = searchParams.get('preload');
  const returnTo = searchParams.get('returnTo');
  const questionIndex = searchParams.get('questionIndex');
  const subject = searchParams.get('subject');
  
  const queryMutation = useMutation({
    mutationFn: async (data) => {
      console.log('[QA] Submitting query:', data);
      try {
        const response = await api.submitQuery(data);
        console.log('[QA] Raw API response:', response);
        return response;
      } catch (error) {
        console.error('[QA] API call failed:', error);
        throw error;
      }
    },
    onSuccess: (response, variables) => {
      console.log('[QA] Query success callback triggered:', response);
      try {
        // Handle different response structures - API returns { success: true, data: {...} }
        const result = response?.data?.data || response?.data || response;
        console.log('[QA] Extracted result:', result);
        
        const answer = result?.answer || result?.response || 'No answer received';
        const confidence = result?.confidence || 'Medium';
        
        // Use the query from the mutation variables, not from state (which might be empty)
        const userQuery = variables.query || query || '';
        
        console.log('[QA] Adding to conversation - user query:', userQuery.substring(0, 50) + '...');
        
        setConversation((prev) => {
          const newConversation = [
            ...prev,
            { type: 'user', content: userQuery },
            { 
              type: 'assistant', 
              content: answer,
              confidence: confidence,
            },
          ];
          console.log('[QA] Conversation updated, length:', newConversation.length);
          return newConversation;
        });
        
        // Clear query after successful submission (user can type new questions)
        setQuery('');
        
        // Always show notification when answer is received (as user requested)
        success('Got an answer! You can now ask another question.');
        
        console.log('[QA] Success handler completed');
      } catch (error) {
        console.error('[QA] Error processing response:', error);
        showError('Received response but failed to process it.');
        // Note: Don't reset here - let onSettled handle it
      }
    },
    onError: (err) => {
      console.error('[QA] Query error callback triggered:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to get answer. Backend may not be running.';
      showError(errorMessage);
      // Clear query on error so user can try again
      setQuery('');
    },
    onSettled: (data, error) => {
      // This runs whether success or error - ensures mutation state is reset
      console.log('[QA] Mutation settled - data:', !!data, 'error:', !!error);
    },
  });

  // Auto-send preloaded query when component mounts (only once)
  useEffect(() => {
    // Only run if we have a preloaded query, haven't sent it yet, user is available, and no conversation exists
    if (preloadedQuery && !preloadSentRef.current && user?.id && conversation.length === 0 && !queryMutation.isPending) {
      // Mark as sent immediately to prevent duplicate submissions
      preloadSentRef.current = true;
      // Set the query in the input field so user can see it
      setQuery(preloadedQuery);
      // Defer the actual mutate() call by a tick. React 18 StrictMode (dev only)
      // double-invokes mount effects synchronously: subscribe -> unsubscribe -> resubscribe.
      // If mutate() runs inside that synchronous window, the in-flight mutation gets
      // attached to the observer that's about to be torn down; the resubscribe never
      // re-attaches it (only mutate() does), so this component's queryMutation.isPending
      // never flips back to false even after the request succeeds - the button/input
      // stay stuck on "Thinking...". Deferring past that window ensures mutate() attaches
      // to the final, stable observer.
      const timeoutId = setTimeout(() => {
        queryMutation.mutate({
          student_id: user.id,
          query: preloadedQuery,
          context: {},
        });
      }, 0);
      // Clear the pending timeout on cleanup so a real unmount (e.g. fast
      // navigation away before the 0ms timer fires) never lets a stale
      // mutate() call fire against a torn-down component. Also reset the
      // "sent" ref: in dev, StrictMode's synchronous mount->cleanup->remount
      // runs this same cleanup, and without resetting the ref the second
      // mount would see preloadSentRef.current already true and skip
      // rescheduling entirely, so the preload would never fire.
      return () => {
        clearTimeout(timeoutId);
        preloadSentRef.current = false;
      };
    }
  }, [preloadedQuery, user?.id]); // Only depend on preloadedQuery and user.id

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    queryMutation.mutate({
      student_id: user.id,
      query: query,
      context: {},
    });
  };

  const handleReturnToPractice = () => {
    if (returnTo === 'practice') {
      // Navigate back to practice with subject and question index
      const params = new URLSearchParams();
      if (subject) params.set('subject', subject);
      if (questionIndex) params.set('questionIndex', questionIndex);
      navigate(`/practice${params.toString() ? '?' + params.toString() : ''}`);
    } else {
      navigate('/practice');
    }
  };

  // Dedupe history against the live conversation: if the just-asked Q&A pair
  // (fired via the preload POST) already landed in `conversation`, the
  // concurrent history GET may return afterward and include the same pair -
  // filter it out of history so it never renders twice. Live wins since it's
  // the fresh entry the user just triggered.
  const pairKey = (question, answer) => `${(question ?? '').length}:${question ?? ''} ${answer ?? ''}`;

  const dedupedHistoryConversation = useMemo(() => {
    const liveConversationPairCounts = new Map();
    for (let i = 0; i < conversation.length - 1; i += 2) {
      const key = pairKey(conversation[i]?.content, conversation[i + 1]?.content);
      liveConversationPairCounts.set(key, (liveConversationPairCounts.get(key) || 0) + 1);
    }

    const deduped = [];
    for (let i = 0; i < historyConversation.length - 1; i += 2) {
      const questionMsg = historyConversation[i];
      const answerMsg = historyConversation[i + 1];
      const key = pairKey(questionMsg?.content, answerMsg?.content);
      const remaining = liveConversationPairCounts.get(key) || 0;
      if (remaining > 0) {
        // A live entry already covers this occurrence - suppress just this one
        // history copy and keep any further repeats of the same question.
        liveConversationPairCounts.set(key, remaining - 1);
      } else {
        deduped.push(questionMsg, answerMsg);
      }
    }
    return deduped;
  }, [conversation, historyConversation]);

  const renderMessage = (msg, key) => (
    <div key={key} className={`qa-message ${msg.type}`}>
      <div className="qa-content">
        {msg.type === 'assistant' ? (
          <ReactMarkdown
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{
              // Style code blocks
              code: ({ inline, className, children, ...props }) => {
                if (inline) {
                  return (
                    <code className="qa-inline-code" {...props}>
                      {children}
                    </code>
                  );
                }
                return (
                  <pre className="qa-code-block">
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </pre>
                );
              },
              // Style paragraphs
              p: ({ children }) => <p className="qa-paragraph">{children}</p>,
              // Style lists
              ul: ({ children }) => <ul className="qa-list">{children}</ul>,
              ol: ({ children }) => <ol className="qa-list">{children}</ol>,
              li: ({ children }) => <li className="qa-list-item">{children}</li>,
              // Style headings
              h1: ({ children }) => <h1 className="qa-heading qa-h1">{children}</h1>,
              h2: ({ children }) => <h2 className="qa-heading qa-h2">{children}</h2>,
              h3: ({ children }) => <h3 className="qa-heading qa-h3">{children}</h3>,
              // Style blockquotes
              blockquote: ({ children }) => <blockquote className="qa-blockquote">{children}</blockquote>,
              // Style links
              a: ({ children, href }) => (
                <a href={href} className="qa-link" target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
              // Style strong and emphasis
              strong: ({ children }) => <strong className="qa-strong">{children}</strong>,
              em: ({ children }) => <em className="qa-emphasis">{children}</em>,
            }}
          >
            {normalizeMathDelimiters(msg.content)}
          </ReactMarkdown>
        ) : (
          <p className="qa-user-message">{msg.content}</p>
        )}
      </div>
      {msg.confidence && (
        <div className="qa-confidence">
          Confidence: <span className={`confidence-${msg.confidence.toLowerCase()}`}>
            {msg.confidence}
          </span>
        </div>
      )}
    </div>
  );

  return (
    <div className="qa">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1 style={{ margin: 0 }}>Curious about something? <span className="inspirational">Let's explore deeper.</span></h1>
        {returnTo === 'practice' && (
          <button
            onClick={handleReturnToPractice}
            style={{
              padding: '0.5rem 1rem',
              fontSize: '0.875rem',
              backgroundColor: 'var(--secondary-color)',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: '500'
            }}
          >
            ← Back to Practice
          </button>
        )}
      </div>
      
      {preloadedQuery && (
        <div style={{
          marginBottom: '1rem',
          padding: '0.75rem',
          backgroundColor: '#d1ecf1',
          border: '1px solid #bee5eb',
          borderRadius: '4px',
          fontSize: '0.875rem',
          color: '#0c5460'
        }}>
          💡 Exploring deeper explanation for your practice question...
        </div>
      )}
      
      {queryMutation.isPending && conversation.length === 0 && (
        <LoadingSpinner message="Thinking..." />
      )}
      
      {historyLoading && conversation.length === 0 && (
        <p className="qa-history-loading">Loading conversation history<span className="ellipsis-dots" /></p>
      )}

      <div className="qa-conversation">
        {conversation.length === 0 && dedupedHistoryConversation.length === 0 && !queryMutation.isPending && !preloadedQuery && !historyLoading && (
          <div className="qa-empty">
            <p>Start a conversation by asking a question below!</p>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
              Try: "How do I solve quadratic equations?" or "Explain photosynthesis"
            </p>
            {historyData?.data?.count === 0 && (
              <p style={{ fontSize: '0.875rem', color: '#666', marginTop: '0.5rem', fontStyle: 'italic' }}>
                No previous conversations found. Start a new conversation!
              </p>
            )}
          </div>
        )}
        {dedupedHistoryConversation.length > 0 && (
          <div style={{
            marginBottom: '1rem',
            padding: '0.75rem',
            backgroundColor: '#d1ecf1',
            border: '1px solid #bee5eb',
            borderRadius: '4px',
            fontSize: '0.875rem',
            color: '#0c5460'
          }}>
            💭 Showing conversation history - the AI remembers your previous questions!
          </div>
        )}
        {dedupedHistoryConversation.map((msg, idx) => renderMessage(msg, `hist-${idx}`))}
        {conversation.map((msg, idx) => renderMessage(msg, `live-${idx}`))}
        {/* Invisible element at the bottom for scrolling */}
        <div ref={conversationEndRef} style={{ height: '1px' }} />
      </div>

      <form onSubmit={handleSubmit} className="qa-form">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={queryMutation.isPending ? "Waiting for answer..." : "Ask your question..."}
          disabled={queryMutation.isPending}
          onKeyDown={(e) => {
            // Allow Enter key to submit even if button appears disabled
            if (e.key === 'Enter' && !queryMutation.isPending && query.trim()) {
              handleSubmit(e);
            }
          }}
        />
        <button 
          type="submit" 
          disabled={queryMutation.isPending || !query.trim()}
          style={{
            opacity: (queryMutation.isPending || !query.trim()) ? 0.6 : 1,
            cursor: (queryMutation.isPending || !query.trim()) ? 'not-allowed' : 'pointer',
            minWidth: '100px'
          }}
        >
          {queryMutation.isPending ? 'Thinking...' : 'Ask'}
        </button>
      </form>
      
      {/* Show error state more prominently */}
      {queryMutation.isError && (
        <div style={{
          marginTop: '1rem',
          padding: '0.75rem',
          backgroundColor: '#f8d7da',
          border: '1px solid #f5c6cb',
          borderRadius: '4px',
          color: '#721c24',
          fontSize: '0.875rem'
        }}>
          <strong>Error:</strong> {queryMutation.error?.response?.data?.detail || queryMutation.error?.message || 'Failed to get answer. Please try again.'}
          <button
            onClick={() => {
              queryMutation.reset();
              setQuery('');
            }}
            style={{
              marginLeft: '1rem',
              padding: '0.25rem 0.5rem',
              fontSize: '0.75rem',
              backgroundColor: '#721c24',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Reset
          </button>
        </div>
      )}
    </div>
  );
}

export default QA;

