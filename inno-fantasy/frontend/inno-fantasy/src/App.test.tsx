import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the FantasyXI home page', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: /FantasyXI skill operations/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Submit skill/i })).toBeInTheDocument();
});
