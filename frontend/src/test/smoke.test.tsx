import { expect, test } from 'vitest';
import { render, screen } from '@testing-library/react';

test('react + jsdom + jest-dom pipeline works', () => {
  render(<div>hello</div>);
  expect(screen.getByText('hello')).toBeVisible();
});
