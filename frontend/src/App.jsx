import { useEffect, useState } from "react";

function App() {
  const [message, setMessage] = useState("Loading...");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/ping")
      .then((res) => {
        if (!res.ok) throw new Error("Network response was not ok");
        return res.json();
      })
      .then((data) => setMessage(JSON.stringify(data)))
      .catch((err) => setMessage("Error: " + err.message));
  }, []);

  return (
    <div style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>Frontend up!</h1>
      <p>Backend says: {message}</p>
    </div>
  );
}

export default App;
