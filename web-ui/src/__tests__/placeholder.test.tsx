/**
 * Placeholder tests to verify test infrastructure works.
 */

import { render, screen } from '@testing-library/react';

import Home from '../app/page';

describe('Test Infrastructure', () => {
  it('placeholder test passes', () => {
    expect(true).toBe(true);
  });

  it('renders home page', () => {
    render(<Home />);
    expect(screen.getByText('Obsidian-Memory')).toBeInTheDocument();
  });
});
