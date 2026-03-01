function alpha(x) {
  if (x > 2 && x < 9) {
    return beta(x);
  }
  return x;
}

const beta = (y) => {
  for (let i = 0; i < y; i++) {
    helper(i);
  }
  return y;
};
