import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the Fantasy Cup home page', () => {
  render(<App />);
  expect(screen.getByText(/Inno Fantasy Cup/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Submit skill/i })).toBeInTheDocument();
});
