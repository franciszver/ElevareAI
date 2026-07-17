import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/apiClient';
import LoadingSpinner from '../components/LoadingSpinner';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import './Dashboard.css';

function Dashboard() {
  const { user } = useAuth();
  const [hideCompleted, setHideCompleted] = useState(false);

  const { data: progress, isLoading: progressLoading, error: progressError } = useQuery({
    queryKey: ['progress', user?.id],
    queryFn: () => {
      console.log('[DASHBOARD] Fetching progress for user:', user.id);
      return api.getProgress(user.id).then(res => {
        console.log('[DASHBOARD] Progress response:', res.data);
        return res.data;
      });
    },
    enabled: !!user?.id,
    retry: false, // Don't retry on error in development
    onError: (error) => {
      console.error('[DASHBOARD] Progress API error:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
        url: error.config?.url,
        userId: user?.id
      });
    }
  });

  const { data: nudgesData, isLoading: nudgesLoading } = useQuery({
    queryKey: ['nudges', user?.id],
    queryFn: () => {
      console.log('[DASHBOARD] Fetching nudges for user:', user.id);
      return api.getNudges(user.id).then(res => {
        console.log('[DASHBOARD] Nudges response:', res.data);
        return res.data;
      });
    },
    enabled: !!user?.id,
    retry: false,
    onError: (error) => {
      console.error('[DASHBOARD] Nudges API error:', error);
    }
  });

  if (progressLoading || nudgesLoading) {
    return (
      <div className="dashboard">
        <LoadingSpinner message="Loading dashboard..." />
      </div>
    );
  }

  const nudges = nudgesData?.data?.nudges || [];
  // Backend returns 'type' not 'nudge_type'
  const inactivityNudge = nudges.find(n => n.type === 'inactivity');
  const otherNudges = nudges.filter(n => n.type !== 'inactivity');

  return (
    <div className="dashboard">
      <h1 className="dashboard-title">
        Welcome back! <span className="inspirational">Let's lift your learning today.</span>
      </h1>
      
      {progressError && (
        <div style={{ 
          background: '#fff3cd', 
          padding: '1rem', 
          marginBottom: '1rem', 
          borderRadius: '4px',
          border: '1px solid var(--primary-light)'
        }}>
          <strong>Note:</strong> API calls are failing (expected in development with mock authentication). 
          The backend needs to be running and configured for API calls to work.
        </div>
      )}

      {/* Inactivity Nudge - Gentle, Supportive Display */}
      {inactivityNudge && (
        <div className="nudge-card inactivity-nudge">
          <div className="nudge-header">
            <span className="nudge-icon">💙</span>
            <h3>A gentle reminder</h3>
          </div>
          <p className="nudge-message">
            It's been a little while — want to lift your confidence today?
          </p>
          {inactivityNudge.suggestions && inactivityNudge.suggestions.length > 0 && (
            <div className="nudge-suggestions">
              <strong>Suggested Actions:</strong>
              <ul>
                {inactivityNudge.suggestions.map((suggestion, idx) => (
                  <li key={idx}>
                    {suggestion.includes('Schedule') || suggestion.includes('session') ? (
                      <button 
                        className="nudge-action-btn primary"
                        onClick={() => {
                          // Navigate to a booking page or show booking modal
                          // For now, just show an alert
                          alert('This would open the session booking page. In production, this would integrate with your booking system.');
                        }}
                      >
                        {suggestion}
                      </button>
                    ) : (
                      <span>{suggestion}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Other Nudges */}
      {otherNudges.length > 0 && (
        <div className="nudges-section">
          {otherNudges.map((nudge, idx) => (
            <div key={idx} className="nudge-card">
              <div className="nudge-header">
                <span className="nudge-icon">✨</span>
                <h3>{nudge.type === 'goal_completion' ? "You've reached your goal!" : 'A friendly suggestion'}</h3>
              </div>
              <p className="nudge-message">{nudge.message}</p>
              {nudge.suggestions && nudge.suggestions.length > 0 && (
                <div className="nudge-suggestions">
                  <ul>
                    {nudge.suggestions.map((suggestion, sIdx) => (
                      <li key={sIdx}>{suggestion}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      
      <div className="dashboard-grid">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ margin: 0 }}>Your Progress</h2>
            {progress?.data?.goals && progress.data.goals.length > 0 && (
              <button
                onClick={() => setHideCompleted(!hideCompleted)}
                style={{
                  padding: '0.5rem 1rem',
                  fontSize: '0.875rem',
                  backgroundColor: hideCompleted ? 'var(--primary-color)' : 'var(--bg-secondary)',
                  color: hideCompleted ? 'white' : 'var(--text-primary)',
                  border: `1px solid ${hideCompleted ? 'var(--primary-color)' : 'var(--border-color)'}`,
                  borderRadius: 'var(--border-radius-sm)',
                  cursor: 'pointer',
                  fontWeight: '500',
                  transition: 'all 0.2s'
                }}
              >
                {hideCompleted ? 'Show Completed' : 'Hide Completed'}
              </button>
            )}
          </div>
          {progress?.data ? (() => {
            let goals = progress.data.goals || [];
            
            // Filter out completed goals if hideCompleted is true
            if (hideCompleted) {
              goals = goals.filter(goal => goal.status !== 'completed');
            }
            
            // Calculate color based on completion percentage
            // Gradient from blue (0%) to green (100%) - matching Goals page progress bars
            const getCompletionColor = (completion) => {
              const percentage = Math.max(0, Math.min(100, completion || 0)) / 100;
              
              // Blue: #4A90E2 (primary-color)
              // Green: #7ED321 (secondary-color)
              const blue = { r: 74, g: 144, b: 226 };
              const green = { r: 126, g: 211, b: 33 };
              
              // Interpolate between blue and green based on completion
              const r = Math.round(blue.r + (green.r - blue.r) * percentage);
              const g = Math.round(blue.g + (green.g - blue.g) * percentage);
              const b = Math.round(blue.b + (green.b - blue.b) * percentage);
              
              return `rgb(${r}, ${g}, ${b})`;
            };
            
            // Prepare data for pie chart - one segment per goal
            const chartData = goals.map((goal, index) => {
              const completion = goal.completion_percentage || 0;
              return {
                name: goal.title || `Goal ${index + 1}`,
                value: completion,
                color: getCompletionColor(completion),
                status: goal.status || 'active',
                completion: completion,
                subject: goal.subject || 'Unknown Subject',
                eloRating: goal.elo_rating
              };
            });
            
            const totalGoals = goals.length;
            
            return (
              <div className="progress-chart-container">
                {totalGoals > 0 ? (
                  <>
                    <ResponsiveContainer width="100%" height={300}>
                      <PieChart>
                        <Pie
                          data={chartData}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ value }) => {
                            // Show only completion percentage on chart to avoid cutoff
                            // Full name will be shown in tooltip
                            if (value > 0) {
                              return `${value.toFixed(0)}%`;
                            }
                            return '';
                          }}
                          outerRadius={55}
                          innerRadius={20}
                          fill="#8884d8"
                          dataKey="value"
                          paddingAngle={3}
                        >
                          {chartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip 
                          content={({ active, payload }) => {
                            if (active && payload && payload.length) {
                              const data = payload[0];
                              const goalName = data.name;
                              const completion = data.payload.completion || 0;
                              const status = data.payload.status || 'active';
                              const subject = data.payload.subject || 'Unknown';
                              const eloRating = data.payload.eloRating;
                              
                              return (
                                <div style={{
                                  backgroundColor: 'white',
                                  padding: '0.75rem',
                                  borderRadius: 'var(--border-radius-sm)',
                                  boxShadow: 'var(--shadow)',
                                  border: '1px solid var(--border-color)',
                                  minWidth: '200px'
                                }}>
                                  <div style={{ 
                                    fontWeight: '600', 
                                    color: 'var(--text-primary)',
                                    marginBottom: '0.5rem',
                                    fontSize: '0.875rem'
                                  }}>
                                    {goalName}
                                  </div>
                                  <div style={{ 
                                    fontSize: '0.75rem', 
                                    color: 'var(--text-secondary)',
                                    marginBottom: '0.25rem'
                                  }}>
                                    <strong>Status:</strong> {status.charAt(0).toUpperCase() + status.slice(1)}
                                  </div>
                                  <div style={{ 
                                    fontSize: '0.75rem', 
                                    color: 'var(--text-secondary)',
                                    marginBottom: '0.25rem'
                                  }}>
                                    <strong>Completion:</strong> {completion.toFixed(0)}%
                                  </div>
                                  <div style={{ 
                                    fontSize: '0.75rem', 
                                    color: 'var(--text-secondary)',
                                    marginBottom: '0.25rem'
                                  }}>
                                    <strong>Subject:</strong> {subject}
                                  </div>
                                  {eloRating !== undefined && eloRating !== null && (
                                    <div style={{ 
                                      fontSize: '0.75rem', 
                                      color: 'var(--text-secondary)',
                                      marginTop: '0.5rem',
                                      paddingTop: '0.5rem',
                                      borderTop: '1px solid var(--border-light)'
                                    }}>
                                      <strong>Elo Rating:</strong> {eloRating}
                                    </div>
                                  )}
                                </div>
                              );
                            }
                            return null;
                          }}
                        />
                        <Legend 
                          verticalAlign="bottom"
                          height={36}
                          formatter={(value, entry) => {
                            // Access completion from the entry payload
                            const completion = entry?.payload?.completion || 0;
                            return `${value} (${completion.toFixed(0)}%)`;
                          }}
                          iconType="circle"
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </>
                ) : (
                  <div className="no-goals-message">
                    <p>No goals yet</p>
                    <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                      Create your first goal to start tracking progress!
                    </p>
                    <Link to="/goals" className="action-link" style={{ marginTop: '1rem', display: 'inline-block' }}>
                      Create Goal
                    </Link>
                  </div>
                )}
              </div>
            );
          })() : (
            <div>
              <p>Getting your progress ready...</p>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                {progressError ? 'Connecting to your data...' : 'Loading...'}
              </p>
            </div>
          )}
        </div>

        <div className="card">
          <h2>What would you like to explore?</h2>
          <div className="actions">
            <Link to="/practice" className="action-link">Start Practice</Link>
            <Link to="/qa" className="action-link">Ask a Question</Link>
            <Link to="/progress" className="action-link">View Progress</Link>
            <Link to="/goals" className="action-link">Manage Goals</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;

