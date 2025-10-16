/**
 * Scene Editor component for editing 3D scenes.
 */

import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { scenesAPI } from '../../api/scenes';
import { SceneViewer } from './SceneViewer';
import type { Scene, SceneObject } from '../../types';

export function SceneEditor() {
  const { sceneId } = useParams<{ sceneId: string }>();
  const [scene, setScene] = useState<Scene | null>(null);
  const [selectedObject, setSelectedObject] = useState<SceneObject | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (sceneId) {
      loadScene(sceneId);
    }
  }, [sceneId]);

  const loadScene = async (id: string) => {
    try {
      const data = await scenesAPI.get(id);
      setScene(data);
    } catch (error) {
      console.error('Failed to load scene:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddCube = async () => {
    if (!sceneId) return;

    try {
      const newObject = await scenesAPI.addObject(sceneId, {
        object_type: 'ASSET',
        name: `Cube_${Date.now()}`,
        position_x: 0,
        position_y: 0,
        position_z: 0,
      });

      setScene((prev) => prev ? {
        ...prev,
        objects: [...prev.objects, newObject],
      } : null);
    } catch (error) {
      console.error('Failed to add object:', error);
    }
  };

  const handleObjectSelect = (obj: SceneObject) => {
    setSelectedObject(obj);
  };

  const handleUpdateObject = async (updates: Partial<SceneObject>) => {
    if (!sceneId || !selectedObject) return;

    try {
      const updated = await scenesAPI.updateObject(sceneId, {
        object_id: selectedObject.id,
        ...updates,
      });

      setScene((prev) => prev ? {
        ...prev,
        objects: prev.objects.map((obj) =>
          obj.id === updated.id ? updated : obj
        ),
      } : null);

      setSelectedObject(updated);
    } catch (error) {
      console.error('Failed to update object:', error);
    }
  };

  if (loading) {
    return <div>Loading scene...</div>;
  }

  if (!scene) {
    return <div>Scene not found</div>;
  }

  return (
    <div className="scene-editor">
      <div className="scene-header">
        <h2>{scene.name}</h2>
        <button onClick={handleAddCube}>Add Cube</button>
      </div>

      <div className="scene-content">
        <div className="scene-viewport">
          <SceneViewer
            objects={scene.objects}
            onObjectSelect={handleObjectSelect}
          />
        </div>

        <div className="scene-properties">
          {selectedObject ? (
            <div>
              <h3>Object Properties</h3>
              <p><strong>Name:</strong> {selectedObject.name}</p>
              <p><strong>Type:</strong> {selectedObject.object_type}</p>

              <div className="property-group">
                <h4>Position</h4>
                <label>
                  X: <input
                    type="number"
                    value={selectedObject.position_x}
                    onChange={(e) => handleUpdateObject({ position_x: parseFloat(e.target.value) })}
                  />
                </label>
                <label>
                  Y: <input
                    type="number"
                    value={selectedObject.position_y}
                    onChange={(e) => handleUpdateObject({ position_y: parseFloat(e.target.value) })}
                  />
                </label>
                <label>
                  Z: <input
                    type="number"
                    value={selectedObject.position_z}
                    onChange={(e) => handleUpdateObject({ position_z: parseFloat(e.target.value) })}
                  />
                </label>
              </div>
            </div>
          ) : (
            <p>Select an object to edit its properties</p>
          )}
        </div>
      </div>
    </div>
  );
}
