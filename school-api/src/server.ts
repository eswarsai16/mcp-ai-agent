import app from './app.js';
import dotenv from 'dotenv';
dotenv.config();

const port = Number(process.env.PORT || 3000);

app.listen(port, () => {
  console.log(`Server running on http://localhost:${port}`);
});
