/**
 * Main Dashboard component showing user's projects.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { projectsAPI } from '../../api/projects';
import type { Project } from '../../types';

export function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      setLoading(true);
      const data = await projectsAPI.list();
      setProjects(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="dashboard-loading">Loading projects...</div>;
  }

  if (error) {
    return <div className="dashboard-error">Error: {error}</div>;
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>My Projects</h1>
        <Link to="/projects/new" className="btn-primary">
          New Project
        </Link>
      </div>

      <div className="projects-grid">
        {projects.length === 0 ? (
          <div className="empty-state">
            <p>No projects yet. Create your first movie!</p>
          </div>
        ) : (
          projects.map((project) => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className="project-card"
            >
              {project.thumbnail && (
                <img
                  src={project.thumbnail}
                  alt={project.title}
                  className="project-thumbnail"
                />
              )}
              <div className="project-info">
                <h3>{project.title}</h3>
                <p>{project.description}</p>
                <div className="project-meta">
                  <span>{project.scenes_count} scenes</span>
                  <span>{project.fps}fps</span>
                  <span>{project.resolution_width}x{project.resolution_height}</span>
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
