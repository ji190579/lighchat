# faq_handler.py
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json
import os
from datetime import datetime

class FAQHandler:
    def __init__(self):
        # ✅ Your correct local model path
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        
        print("Loading sentence transformer model...")
        try:
            self.model = SentenceTransformer(model_name)
            print("✅ Model loaded successfully")
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            raise


        import sys
        import os
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
        from data.faq import FAQ_DATABASE

        self.faqs = FAQ_DATABASE  # Load FAQs from py file
        
           
        
        print(f"Encoding {len(self.faqs)} FAQ questions...")
        self.faq_questions = [faq["question"] for faq in self.faqs]
        self.faq_embeddings = self.model.encode(self.faq_questions)
        print(f"✅ {len(self.faqs)} FAQ embeddings ready")
    
    def find_answer(self, user_question, threshold=0.65):
        """
        Find best matching FAQ
        
        Args:
            user_question: User's input
            threshold: Minimum similarity score (0-1)
        
        Returns:
            dict with answer, score, matched_question, source
        """
        try:
            user_embedding = self.model.encode([user_question])
            similarities = cosine_similarity(user_embedding, self.faq_embeddings)[0]
            
            # Get top 3 matches
            top_3_indices = similarities.argsort()[-3:][::-1]
            top_3_matches = [
                {
                    "question": self.faq_questions[i],
                    "score": float(similarities[i])
                }
                for i in top_3_indices
            ]
            
            best_idx = similarities.argmax()
            best_score = float(similarities[best_idx])
            
            # Log query
            self._log_query(user_question, top_3_matches, threshold)
            
            if best_score >= threshold:
                print(f"✅ FAQ HIT: '{self.faq_questions[best_idx]}' ({best_score:.2%})")
                return {
                    "answer": self.faqs[best_idx]["answer"],
                    "score": best_score,
                    "matched_question": self.faq_questions[best_idx],
                    "source": "FAQ",
                    "top_3": top_3_matches
                }
            else:
                print(f"❌ No FAQ match. Best: '{self.faq_questions[best_idx]}' ({best_score:.2%})")
                return {
                    "answer": None,
                    "score": best_score,
                    "matched_question": self.faq_questions[best_idx],
                    "source": "NO_MATCH",
                    "top_3": top_3_matches
                }
        
        except Exception as e:
            print(f"❌ Error in find_answer: {e}")
            return {
                "answer": None,
                "score": 0.0,
                "source": "ERROR"
            }
    
    def _log_query(self, user_question, top_3_matches, threshold):
        """Log all FAQ queries for analysis"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_question": user_question,
            "top_3_matches": top_3_matches,
            "threshold": threshold,
            "hit": top_3_matches[0]["score"] >= threshold
        }
        
        os.makedirs("logs", exist_ok=True)
        with open("logs/faq_queries.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


# ✅ Test the handler
if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing FAQ Handler")
    print("="*60)
    
    handler = FAQHandler()
    
    test_questions = [
        "What's your Java experience?",
        "Tell me about PowerBuilder",
        "Do you know Docker?",
        "What AI projects have you done?",
        "Where are you from?",
        "What's the weather like today?"  # Should not match
    ]
    
    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        result = handler.find_answer(q, threshold=0.65)
        if result["answer"]:
            print(f"✅ A: {result['answer'][:100]}...")
            print(f"   Score: {result['score']:.2%}")
        else:
            print(f"❌ No match (score: {result['score']:.2%})")