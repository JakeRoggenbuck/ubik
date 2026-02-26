(import collections [Counter])

(defn hello []
	"Hello, from Hy!")

(with [f (open "good.txt" "r")]
  (setv good_lines (.readlines f)))

(with [f (open "bad.txt" "r")]
  (setv bad_lines (.readlines f)))

(setv good_counter (Counter))
(setv bad_counter (Counter))

(defn create_map [lines counter]
    (for [line lines]
      (.update counter (.split line)))
    counter)

(defn make_maps []
  [(create_map good_lines good_counter) (create_map bad_lines bad_counter)])

(make_maps)

;; Default the value to 0.5 if it's not found
;; Should it really be 0.5 out of the gate, or should
;; r_good be 0.5 if it's not found? Maybe that's my issue
(defn safe_get [counter w]
  (let [v (get counter w)]
    (if (= v 0)
        0.5
        v)))

(defn r_good [w]
  (min 1 (* 2 (/ (safe_get good_counter w) (len good_counter)))))

(defn r_bad [w]
  (min 1 (/ (safe_get bad_counter w) (len bad_counter))))

;; Word that is present should be greater than 0
(assert (> (safe_get bad_counter "INTERESTED") 0))
;; Word that is not present should also be greater than 0
(assert (> (safe_get bad_counter "FOO") 0))

(assert (> (r_bad "INTERESTED") 0))
;; Words not present should not be zero
(assert (!= (r_bad "FOOBAR") 0))

(defn p_spam [w]
  (max 0.01
       (min 0.99 (/
                    (r_bad w)
                    (+
                      (r_bad w)
                      (r_good w))))))

(defn recip_p_spam [w]
  (- 1 (p_spam w)))

;; P.G. has a specific algorithm, but I'm going to try average
;; Turns out this is really bad, because it usually just scores low
;; even for messages that are completely in the bad data set.
;; It seems like it's important to get the 15 most important words
;; and use those for the calculation.
;;
;; It's also likely that I need a much bigger training data set.
;; Currently, it's at like ~10-20 messages per class
(defn naive_classify_message [message]
  (setv words (.split message)
      scores (map p_spam words))
  (/ (sum scores) (len message)))

(defn top_15_words [words]
    (cut (list (reversed
                 (sorted words :key
                         (fn [x] (abs (- x 0.5)))))) 0 15))

;; This does an average of the top 15 most important words
(defn p_spam_message [message]
  (setv words (.split message)
      scores (top_15_words (map p_spam words)))
  (/ (sum scores) (len scores)))

(defn recip_p_spam_message [message]
  (setv words (.split message)
      scores (top_15_words (map recip_p_spam words)))
  (/ (sum scores) (len scores)))

;; This is exactly what P.G. wrote for his spam filter
;; Something seems broken, because I only get values from ~0.44-0.66
;; Maybe it's likely that I purely just don't have enough training data
;; I have like 20 words per class, and that's probably just not enough
;; That being said, spam does appear to have high scores and non-spam low
(defn classify_message [message]
  (/ (p_spam_message message)
     (+ (p_spam_message message) (recip_p_spam_message message))))
